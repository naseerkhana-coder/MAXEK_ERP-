"""Office correspondence — inward/outward letters, drafting, approvals, email inbox."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.correspondence_data import (
    AUTHORITY_TYPES,
    DEPARTMENTS,
    DRAFT_STATUSES,
    INWARD_STATUSES,
    LETTER_TEMPLATES,
    OUTWARD_STATUSES,
    PRIORITIES,
    RECEIVED_THROUGH,
    SENT_THROUGH,
    advance_draft_approval,
    authority_pending_buckets,
    correspondence_dashboard_stats,
    create_inward_from_email,
    draft_to_outward,
    fetch_imap_inbox,
    get_authority,
    get_draft,
    get_inward,
    get_outward,
    load_archive,
    load_authority_tracking,
    load_correspondence_audit,
    load_drafts,
    load_email_inbox,
    load_inward_letters,
    load_outward_letters,
    load_reply_tracking,
    mark_email_processed,
    save_authority,
    save_draft,
    save_inward,
    save_outward,
    void_inward,
)
from modules.database import DATE_FMT, DATE_INPUT_FMT, load_project_names
from modules.pages import _save_upload
from modules.roles import is_management, is_super_admin


def _actor() -> str:
    return st.session_state.get("user_name", "User")


def _role() -> str:
    return st.session_state.get("user_role", "Admin")


def _date_str(d) -> str:
    if not d:
        return ""
    return d.strftime(DATE_FMT) if hasattr(d, "strftime") else str(d)


def _parse_date(text: str):
    if not text:
        return datetime.now().date()
    for fmt in (DATE_FMT, "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return datetime.now().date()


def _save_corr_upload(uploaded, prefix: str) -> str:
    return _save_upload(uploaded, "uploads/correspondence", prefix)


def page_corr_dashboard():
    st.subheader("Correspondence Dashboard")
    st.caption("Incoming letters, replies, authority submissions, and email inbox.")

    stats = correspondence_dashboard_stats()
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Received today", stats.get("received_today", 0))
    c2.metric("Replied today", stats.get("replied_today", 0))
    c3.metric("Pending reply", stats.get("pending_reply", 0))
    c4.metric("Urgent", stats.get("urgent", 0))
    c5.metric("Authority pending", stats.get("authority_pending", 0))
    c6.metric("Unprocessed email", stats.get("unprocessed_email", 0))

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Recent inward (pending)**")
        df = load_inward_letters(status=None, limit=15)
        if df.empty:
            st.info("No inward letters yet.")
        else:
            pending = df[df["status"].isin(["Received", "Under Review", "Reply Pending"])]
            st.dataframe(
                pending.head(10) if not pending.empty else df.head(10),
                use_container_width=True,
                hide_index=True,
            )
    with col_b:
        st.markdown("**Drafts awaiting approval**")
        drafts = load_drafts(status=None, limit=15)
        if drafts.empty:
            st.info("No letter drafts.")
        else:
            pending_d = drafts[drafts["status"].str.contains("Pending", na=False)]
            st.dataframe(
                pending_d.head(10) if not pending_d.empty else drafts.head(10),
                use_container_width=True,
                hide_index=True,
            )


def _inward_form(row: dict | None):
    row = row or {}
    projects = [""] + load_project_names()
    with st.form("corr_inward_form"):
        c1, c2 = st.columns(2)
        date_received = c1.date_input(
            "Date received",
            value=_parse_date(row.get("date_received", "")),
            format=DATE_INPUT_FMT,
        )
        received_through = c2.selectbox(
            "Received through",
            RECEIVED_THROUGH,
            index=RECEIVED_THROUGH.index(row.get("received_through", "Email"))
            if row.get("received_through") in RECEIVED_THROUGH
            else 0,
        )
        c3, c4 = st.columns(2)
        from_party = c3.text_input("From (party / organisation)", value=row.get("from_party", ""))
        contact_number = c4.text_input("Contact number", value=row.get("contact_number", ""))
        email_id = st.text_input("Email", value=row.get("email_id", ""))
        subject = st.text_input("Subject", value=row.get("subject", ""))
        project_related = st.checkbox("Project related", value=bool(row.get("project_related")))
        project_name = st.selectbox(
            "Project",
            projects,
            index=projects.index(row.get("project_name", "")) if row.get("project_name") in projects else 0,
        )
        c5, c6, c7 = st.columns(3)
        department = c5.selectbox(
            "Department",
            DEPARTMENTS,
            index=DEPARTMENTS.index(row.get("department", "Admin"))
            if row.get("department") in DEPARTMENTS
            else 0,
        )
        priority = c6.selectbox(
            "Priority",
            PRIORITIES,
            index=PRIORITIES.index(row.get("priority", "Medium"))
            if row.get("priority") in PRIORITIES
            else 1,
        )
        status = c7.selectbox(
            "Status",
            INWARD_STATUSES,
            index=INWARD_STATUSES.index(row.get("status", "Received"))
            if row.get("status") in INWARD_STATUSES
            else 0,
        )
        description = st.text_area("Description / summary", value=row.get("description", ""))
        c8, c9 = st.columns(2)
        assigned_to = c8.text_input("Assigned to", value=row.get("assigned_to", ""))
        due_date = c9.date_input(
            "Due date",
            value=_parse_date(row.get("due_date", "")) if row.get("due_date") else None,
            format=DATE_INPUT_FMT,
        )
        related_outward = st.text_input("Related outward no.", value=row.get("related_outward_no", ""))
        attachment = st.file_uploader("Attachment", key=f"inw_att_{row.get('inward_id', 'new')}")
        if st.form_submit_button("SAVE INWARD", type="primary", use_container_width=True):
            if not subject.strip():
                st.error("Subject is required.")
            else:
                att_path = row.get("attachment", "")
                if attachment:
                    att_path = _save_corr_upload(attachment, row.get("inward_id") or "inw")
                iid, ino = save_inward(
                    {
                        "inward_id": row.get("inward_id"),
                        "inward_no": row.get("inward_no"),
                        "date_received": _date_str(date_received),
                        "received_through": received_through,
                        "from_party": from_party.strip(),
                        "contact_number": contact_number.strip(),
                        "email_id": email_id.strip(),
                        "subject": subject.strip(),
                        "project_related": project_related,
                        "project_name": project_name if project_related else "",
                        "department": department,
                        "priority": priority,
                        "description": description.strip(),
                        "attachment": att_path,
                        "assigned_to": assigned_to.strip(),
                        "due_date": _date_str(due_date) if due_date else "",
                        "status": status,
                        "related_outward_no": related_outward.strip(),
                        "source_email_uid": row.get("source_email_uid", ""),
                    },
                    _actor(),
                )
                st.success(f"Inward saved: {ino} ({iid})")
                st.session_state.pop("corr_edit_inward_id", None)
                st.rerun()


def page_corr_incoming():
    st.subheader("Incoming Letter Register")
    st.caption("Register inward letters with INW document numbers.")

    tab_list, tab_add = st.tabs(["Register", "Add / Edit"])
    with tab_list:
        c1, c2 = st.columns([1, 2])
        status_f = c1.selectbox("Status filter", ["All"] + INWARD_STATUSES, key="inw_status_f")
        search = c2.text_input("Search", key="inw_search")
        df = load_inward_letters(status=status_f, search=search)
        if df.empty:
            st.info("No inward letters match your filters.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            options = df["inward_id"].tolist()
            sel = st.selectbox("Open for edit", ["—"] + options, key="inw_pick_edit")
            if sel != "—":
                if st.button("Edit selected inward", key="inw_go_edit"):
                    st.session_state["corr_edit_inward_id"] = sel
                    st.rerun()

    with tab_add:
        edit_id = st.session_state.get("corr_edit_inward_id")
        row = get_inward(edit_id) if edit_id else {}
        if edit_id and row:
            st.info(f"Editing {row.get('inward_no', edit_id)}")
            if st.button("Clear selection", key="inw_clear_edit"):
                st.session_state.pop("corr_edit_inward_id", None)
                st.rerun()
        _inward_form(row)
        if edit_id and row and is_super_admin(_role()):
            reason = st.text_input("Void reason", key="inw_void_reason")
            if st.button("Void inward", key="inw_void_btn"):
                void_inward(edit_id, _actor(), reason)
                st.session_state.pop("corr_edit_inward_id", None)
                st.warning("Inward voided.")
                st.rerun()


def _outward_form(row: dict | None):
    row = row or {}
    projects = [""] + load_project_names()
    with st.form("corr_outward_form"):
        c1, c2 = st.columns(2)
        date_sent = c1.date_input(
            "Date sent",
            value=_parse_date(row.get("date_sent", "")),
            format=DATE_INPUT_FMT,
        )
        status = c2.selectbox(
            "Status",
            OUTWARD_STATUSES,
            index=OUTWARD_STATUSES.index(row.get("status", "Draft"))
            if row.get("status") in OUTWARD_STATUSES
            else 0,
        )
        recipient = st.text_input("Recipient", value=row.get("recipient", ""))
        subject = st.text_input("Subject", value=row.get("subject", ""))
        related_inward = st.text_input("Related inward no. (INW-…)", value=row.get("related_inward_no", ""))
        project_name = st.selectbox(
            "Project",
            projects,
            index=projects.index(row.get("project_name", "")) if row.get("project_name") in projects else 0,
        )
        c3, c4 = st.columns(2)
        sent_through = c3.selectbox(
            "Sent through",
            SENT_THROUGH,
            index=SENT_THROUGH.index(row.get("sent_through", "Email"))
            if row.get("sent_through") in SENT_THROUGH
            else 0,
        )
        template_type = c4.selectbox(
            "Template",
            LETTER_TEMPLATES,
            index=LETTER_TEMPLATES.index(row.get("template_type", "Company Letter"))
            if row.get("template_type") in LETTER_TEMPLATES
            else 0,
        )
        reference_number = st.text_input("Reference number", value=row.get("reference_number", ""))
        letter_content = st.text_area("Letter content", value=row.get("letter_content", ""), height=200)
        attachment = st.file_uploader("Attachment", key=f"out_att_{row.get('outward_id', 'new')}")
        delivery_proof = st.file_uploader("Delivery proof", key=f"out_del_{row.get('outward_id', 'new')}")
        if st.form_submit_button("SAVE OUTWARD", type="primary", use_container_width=True):
            if not recipient.strip() or not subject.strip():
                st.error("Recipient and subject are required.")
            else:
                att = row.get("attachment", "")
                if attachment:
                    att = _save_corr_upload(attachment, row.get("outward_id") or "out")
                proof = row.get("delivery_proof", "")
                if delivery_proof:
                    proof = _save_corr_upload(delivery_proof, f"{row.get('outward_id') or 'out'}_proof")
                oid, ono = save_outward(
                    {
                        "outward_id": row.get("outward_id"),
                        "outward_no": row.get("outward_no"),
                        "date_sent": _date_str(date_sent),
                        "recipient": recipient.strip(),
                        "subject": subject.strip(),
                        "related_inward_no": related_inward.strip(),
                        "project_name": project_name,
                        "sent_through": sent_through,
                        "attachment": att,
                        "delivery_proof": proof,
                        "letter_content": letter_content.strip(),
                        "template_type": template_type,
                        "reference_number": reference_number.strip(),
                        "status": status,
                    },
                    _actor(),
                )
                st.success(f"Outward saved: {ono} ({oid})")
                st.session_state.pop("corr_edit_outward_id", None)
                st.rerun()


def page_corr_outgoing():
    st.subheader("Outgoing Letter Register")
    st.caption("Outgoing letters with OUT document numbers.")

    tab_list, tab_add = st.tabs(["Register", "Add / Edit"])
    with tab_list:
        c1, c2 = st.columns([1, 2])
        status_f = c1.selectbox("Status filter", ["All"] + OUTWARD_STATUSES, key="out_status_f")
        search = c2.text_input("Search", key="out_search")
        df = load_outward_letters(status=status_f, search=search)
        if df.empty:
            st.info("No outward letters yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            options = df["outward_id"].tolist()
            sel = st.selectbox("Open for edit", ["—"] + options, key="out_pick_edit")
            if sel != "—" and st.button("Edit selected outward", key="out_go_edit"):
                st.session_state["corr_edit_outward_id"] = sel
                st.rerun()

    with tab_add:
        edit_id = st.session_state.get("corr_edit_outward_id")
        row = get_outward(edit_id) if edit_id else {}
        if edit_id and row:
            st.info(f"Editing {row.get('outward_no', edit_id)}")
            if st.button("Clear selection", key="out_clear_edit"):
                st.session_state.pop("corr_edit_outward_id", None)
                st.rerun()
        _outward_form(row)


def _draft_form(row: dict | None, *, allow_submit: bool = True):
    row = row or {}
    projects = [""] + load_project_names()
    with st.form("corr_draft_form"):
        c1, c2 = st.columns(2)
        draft_date = c1.date_input(
            "Draft date",
            value=_parse_date(row.get("draft_date", "")),
            format=DATE_INPUT_FMT,
        )
        template_type = c2.selectbox(
            "Template",
            LETTER_TEMPLATES,
            index=LETTER_TEMPLATES.index(row.get("template_type", "Company Letter"))
            if row.get("template_type") in LETTER_TEMPLATES
            else 0,
        )
        recipient_to = st.text_input("To", value=row.get("recipient_to", ""))
        subject = st.text_input("Subject", value=row.get("subject", ""))
        reference_number = st.text_input("Reference", value=row.get("reference_number", ""))
        project_name = st.selectbox(
            "Project",
            projects,
            index=projects.index(row.get("project_name", "")) if row.get("project_name") in projects else 0,
        )
        related_inward = st.text_input("Related inward no.", value=row.get("related_inward_no", ""))
        letter_content = st.text_area("Letter body", value=row.get("letter_content", ""), height=220)
        attachment = st.file_uploader("Attachment", key=f"draft_att_{row.get('draft_id', 'new')}")
        status = row.get("status", "Draft")
        st.caption(f"Current status: **{status}**")
        c_save, c_submit = st.columns(2)
        save_btn = c_save.form_submit_button("SAVE DRAFT", use_container_width=True)
        submit_btn = c_submit.form_submit_button("SUBMIT FOR APPROVAL", use_container_width=True) if allow_submit else False
        if save_btn or submit_btn:
            if not subject.strip():
                st.error("Subject is required.")
            else:
                att = row.get("attachment", "")
                if attachment:
                    att = _save_corr_upload(attachment, row.get("draft_id") or "draft")
                new_status = status
                if submit_btn and status == "Draft":
                    new_status = "Pending Dept"
                did, lno = save_draft(
                    {
                        "draft_id": row.get("draft_id"),
                        "letter_no": row.get("letter_no"),
                        "draft_date": _date_str(draft_date),
                        "template_type": template_type,
                        "recipient_to": recipient_to.strip(),
                        "subject": subject.strip(),
                        "reference_number": reference_number.strip(),
                        "project_name": project_name,
                        "letter_content": letter_content.strip(),
                        "attachment": att,
                        "related_inward_no": related_inward.strip(),
                        "status": new_status,
                    },
                    _actor(),
                )
                st.success(f"Draft saved: {lno} ({did})")
                st.session_state.pop("corr_edit_draft_id", None)
                st.rerun()


def page_corr_drafting():
    st.subheader("Letter Drafting")
    st.caption("Compose letters and submit for Dept → GM → MD approval.")

    tab_list, tab_edit = st.tabs(["Draft list", "Compose / Edit"])
    with tab_list:
        status_f = st.selectbox("Status", ["All"] + DRAFT_STATUSES, key="draft_status_f")
        df = load_drafts(status=status_f)
        if df.empty:
            st.info("No drafts yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            options = df["draft_id"].tolist()
            sel = st.selectbox("Edit draft", ["—"] + options, key="draft_pick")
            if sel != "—" and st.button("Open draft", key="draft_open"):
                st.session_state["corr_edit_draft_id"] = sel
                st.rerun()
            approved = df[df["status"] == "Approved"]
            if not approved.empty:
                st.markdown("**Convert approved draft to outward**")
                ap = st.selectbox("Approved draft", approved["draft_id"].tolist(), key="draft_to_out_sel")
                sent_via = st.selectbox("Sent through", SENT_THROUGH, key="draft_sent_via")
                if st.button("Create outward from draft", key="draft_to_out_btn"):
                    oid, ono = draft_to_outward(ap, _actor(), sent_via)
                    if ono:
                        st.success(f"Outward created: {ono}")
                        st.rerun()
                    else:
                        st.error("Draft must be Approved before converting.")

    with tab_edit:
        edit_id = st.session_state.get("corr_edit_draft_id")
        row = get_draft(edit_id) if edit_id else {}
        if edit_id and row:
            st.info(f"Editing {row.get('letter_no', edit_id)} — {row.get('status')}")
            if st.button("New draft", key="draft_clear"):
                st.session_state.pop("corr_edit_draft_id", None)
                st.rerun()
        _draft_form(row, allow_submit=row.get("status", "Draft") in ("Draft", "Rejected", ""))


def page_corr_email():
    st.subheader("Email Inbox")
    st.caption("Fetch from IMAP (info@maxexinindia.com) and link messages to inward register.")

    c1, c2 = st.columns([1, 3])
    if c1.button("Fetch new mail (IMAP)", type="primary", use_container_width=True):
        count, msg = fetch_imap_inbox()
        if count:
            st.success(msg)
        else:
            st.warning(msg)
        st.rerun()
    c2.caption("Enable corr_imap_enabled=1 and set corr_imap_password in app settings.")

    show = st.radio("Show", ["Unprocessed", "All"], horizontal=True, key="email_show")
    processed = False if show == "Unprocessed" else None
    df = load_email_inbox(processed=processed)
    if df.empty:
        st.info("No emails in inbox. Fetch from IMAP or add manually below.")
    else:
        display_cols = [c for c in ["received_at", "from_address", "subject", "processed", "inward_no"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

    with st.expander("Add email manually"):
        with st.form("manual_email"):
            from_addr = st.text_input("From")
            subj = st.text_input("Subject")
            body = st.text_area("Preview")
            if st.form_submit_button("Add to inbox"):
                from modules.correspondence_data import save_email_inbox_row

                save_email_inbox_row(from_addr, subj, body)
                st.success("Added.")
                st.rerun()

    if not df.empty and "email_uid" in df.columns:
        uid = st.selectbox("Link email to inward", df["email_uid"].tolist(), key="email_link_uid")
        row_email = df[df["email_uid"] == uid].iloc[0] if uid else None
        if row_email is not None and not int(row_email.get("processed", 0)):
            if st.button("Create inward from email", key="email_create_inw"):
                iid, ino = create_inward_from_email(uid, _actor())
                if ino:
                    mark_email_processed(uid, ino)
                    st.success(f"Inward {ino} created.")
                    st.rerun()
                else:
                    st.error("Could not create inward.")


def page_corr_approval():
    st.subheader("Letter Approvals")
    st.caption("Department → GM → MD workflow.")

    role = _role()
    df = load_drafts(status=None, limit=100)
    if df.empty:
        st.info("No drafts in the system.")
        return

    pending = df[df["status"].isin(["Pending Dept", "Pending GM", "Pending MD"])]
    if pending.empty:
        st.success("No letters pending approval.")
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    st.dataframe(pending, use_container_width=True, hide_index=True)
    draft_id = st.selectbox("Select draft", pending["draft_id"].tolist(), key="appr_draft_sel")
    d = get_draft(draft_id) or {}
    st.markdown(f"**{d.get('subject', '')}** — {d.get('status')}")
    st.text_area("Letter preview", value=d.get("letter_content", ""), height=160, disabled=True)
    comments = st.text_input("Comments / rejection reason", key="appr_comments")

    c1, c2, c3, c4 = st.columns(4)
    status = d.get("status", "")

    def _do(step):
        if advance_draft_approval(draft_id, step, _actor(), comments):
            st.success("Approval updated.")
            st.rerun()
        else:
            st.error("Could not update approval.")

    if status == "Pending Dept" and (is_management(role) or role in {"Project Manager", "Admin"}):
        if c1.button("Dept approve", key="appr_dept", use_container_width=True):
            _do("dept")
    if status == "Pending GM" and is_management(role):
        if c2.button("GM approve", key="appr_gm", use_container_width=True):
            _do("gm")
    if status == "Pending MD" and is_super_admin(role):
        if c3.button("MD approve", key="appr_md", use_container_width=True):
            _do("md")
    if is_management(role) or is_super_admin(role):
        if c4.button("Reject", key="appr_reject", use_container_width=True):
            _do("reject")


def page_corr_tracking():
    st.subheader("Reply Tracking")
    st.caption("Incoming letters linked to outgoing replies.")

    df = load_reply_tracking()
    if df.empty:
        st.info("No correspondence to track yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        pending = df[df["inward_status"].isin(["Received", "Under Review", "Reply Pending"])]
        if not pending.empty:
            st.warning(f"{len(pending)} letter(s) still awaiting reply.")


def page_corr_authority():
    st.subheader("Authority / Government Correspondence")
    st.caption("Track submissions to authorities and approval status.")

    tab_add, tab_list, tab_buckets = st.tabs(["Add / Edit", "Register", "Pending buckets"])
    projects = [""] + load_project_names()

    with tab_buckets:
        buckets = authority_pending_buckets()
        for label, key in [("0–7 days", "7"), ("8–15 days", "15"), ("16–30 days", "30"), ("Over 30 days", "overdue")]:
            bdf = buckets.get(key, pd.DataFrame())
            st.markdown(f"**{label}** ({len(bdf)} items)")
            if not bdf.empty:
                st.dataframe(bdf, use_container_width=True, hide_index=True)

    with tab_list:
        status_f = st.selectbox("Status", ["", "Pending", "Approved", "Closed"], key="auth_status_f")
        df = load_authority_tracking(status=status_f or None)
        if df.empty:
            st.info("No authority records.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            if "authority_id" in df.columns:
                sel = st.selectbox("Edit record", ["—"] + df["authority_id"].tolist(), key="auth_pick")
                if sel != "—" and st.button("Open", key="auth_open"):
                    st.session_state["corr_edit_authority_id"] = sel
                    st.rerun()

    with tab_add:
        edit_id = st.session_state.get("corr_edit_authority_id")
        row = get_authority(edit_id) if edit_id else {}
        if edit_id and row:
            st.info(f"Editing {row.get('authority_name', edit_id)}")
            if st.button("Clear", key="auth_clear"):
                st.session_state.pop("corr_edit_authority_id", None)
                st.rerun()
        with st.form("authority_form"):
            c1, c2 = st.columns(2)
            authority_name = c1.text_input("Authority name", value=row.get("authority_name", ""))
            authority_type = c2.selectbox(
                "Type",
                AUTHORITY_TYPES,
                index=AUTHORITY_TYPES.index(row.get("authority_type", "Other"))
                if row.get("authority_type") in AUTHORITY_TYPES
                else len(AUTHORITY_TYPES) - 1,
            )
            project_name = st.selectbox(
                "Project",
                projects,
                index=projects.index(row.get("project_name", "")) if row.get("project_name") in projects else 0,
            )
            subject = st.text_input("Subject", value=row.get("subject", ""))
            c3, c4, c5 = st.columns(3)
            submission_date = c3.date_input(
                "Submission date",
                value=_parse_date(row.get("submission_date", "")),
                format=DATE_INPUT_FMT,
            )
            expected_reply = c4.date_input(
                "Expected reply",
                value=_parse_date(row.get("expected_reply_date", "")) if row.get("expected_reply_date") else None,
                format=DATE_INPUT_FMT,
            )
            followup_date = c5.date_input(
                "Follow-up date",
                value=_parse_date(row.get("followup_date", "")) if row.get("followup_date") else None,
                format=DATE_INPUT_FMT,
            )
            approval_received = st.checkbox("Approval received", value=bool(row.get("approval_received")))
            approval_date = st.date_input(
                "Approval date",
                value=_parse_date(row.get("approval_date", "")) if row.get("approval_date") else None,
                format=DATE_INPUT_FMT,
            )
            related_inward = st.text_input("Related inward no.", value=row.get("related_inward_no", ""))
            related_outward = st.text_input("Related outward no.", value=row.get("related_outward_no", ""))
            remarks = st.text_area("Remarks", value=row.get("remarks", ""))
            auth_statuses = ["Pending", "Approved", "Closed"]
            status = st.selectbox(
                "Status",
                auth_statuses,
                index=auth_statuses.index(row.get("status", "Pending"))
                if row.get("status") in auth_statuses
                else 0,
            )
            if st.form_submit_button("SAVE", type="primary", use_container_width=True):
                if not authority_name.strip():
                    st.error("Authority name is required.")
                else:
                    aid = save_authority(
                        {
                            "authority_id": row.get("authority_id"),
                            "authority_name": authority_name.strip(),
                            "authority_type": authority_type,
                            "project_name": project_name,
                            "subject": subject.strip(),
                            "submission_date": _date_str(submission_date),
                            "expected_reply_date": _date_str(expected_reply) if expected_reply else "",
                            "followup_date": _date_str(followup_date) if followup_date else "",
                            "approval_received": approval_received,
                            "approval_date": _date_str(approval_date) if approval_date and approval_received else "",
                            "related_inward_no": related_inward.strip(),
                            "related_outward_no": related_outward.strip(),
                            "remarks": remarks.strip(),
                            "status": "Approved" if approval_received else status,
                        },
                        _actor(),
                    )
                    st.success(f"Saved: {aid}")
                    st.session_state.pop("corr_edit_authority_id", None)
                    st.rerun()


def page_corr_archive():
    st.subheader("Archive & Search")
    st.caption("Closed inward and acknowledged outward letters.")

    search = st.text_input("Search subject or document number", key="arch_search")
    df = load_archive(search=search)
    if df.empty:
        st.info("No archived correspondence found.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("Audit log"):
        audit = load_correspondence_audit(limit=50)
        if audit.empty:
            st.caption("No audit entries yet.")
        else:
            st.dataframe(audit, use_container_width=True, hide_index=True)
