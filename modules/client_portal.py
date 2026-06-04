"""Client portal UI — login, navigation, and scoped client-facing screens."""

from __future__ import annotations

import os

import streamlit as st

from modules.branding import ERP_DISPLAY_NAME, ERP_LOGIN_TITLE, ERP_TAGLINE
from modules.client_portal_db import (
    CLIENT_ROLE,
    add_client_comment,
    approve_client_bill,
    assign_client_project,
    authenticate_portal_user,
    create_portal_user,
    list_assignments,
    list_portal_users,
    load_bills_pending_client_review,
    load_client_invoices,
    load_client_projects,
    load_entity_comments,
    load_payment_history,
    load_progress_reports,
    load_project_documents,
    load_clients_for_admin,
    load_projects_for_assignment,
    log_portal_audit,
    notify_accounts_bill_decision,
    reject_client_bill,
    remove_client_project_assignment,
)
from modules.database import BASE_DIR
from modules.document_pdfs import generate_client_invoice_pdf, generate_project_progress_pdf
from modules.navigation import page_label
from modules.password_security import validate_password_policy

PORTAL_CSS_PATH = os.path.join(BASE_DIR, "styles", "client_portal.css")

CLIENT_MENU: list[tuple[str, str, str]] = [
    ("portal_dash", "Client Dashboard", "🏠"),
    ("portal_projects", "Projects", "🏗️"),
    ("portal_invoices", "Invoices", "🧾"),
    ("portal_bills", "Bills for Approval", "✅"),
    ("portal_documents", "Documents", "📁"),
    ("portal_progress", "Progress Reports", "📈"),
    ("portal_payments", "Payment History", "💳"),
]

CLIENT_PAGE_KEYS = frozenset(k for k, _, _ in CLIENT_MENU)


def is_client_session() -> bool:
    return st.session_state.get("user_role") == CLIENT_ROLE and st.session_state.get("client_id")


def inject_client_portal_css():
    from modules.ui import inject_global_css

    inject_global_css()
    if os.path.isfile(PORTAL_CSS_PATH):
        with open(PORTAL_CSS_PATH, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    st.markdown(
        """
        <script>
        document.body.classList.add('maxek-client-portal');
        </script>
        """,
        unsafe_allow_html=True,
    )


def _portal_context() -> dict:
    return {
        "portal_user_id": st.session_state.get("portal_user_id", ""),
        "client_id": st.session_state.get("client_id", ""),
        "client_name": st.session_state.get("client_name", ""),
        "display_name": st.session_state.get("user_name", "Client"),
    }


def _audit_view(entity_type: str, entity_id: str, details: str = ""):
    ctx = _portal_context()
    log_portal_audit(
        "view",
        portal_user_id=ctx["portal_user_id"],
        client_id=ctx["client_id"],
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )


def show_client_login_form():
    """Client portal login — email or mobile + password."""
    inject_client_portal_css()
    st.markdown('<div class="maxek-login-marker"></div>', unsafe_allow_html=True)
    st.markdown(f"### {ERP_LOGIN_TITLE}")
    st.caption(f"{ERP_TAGLINE} — Client Portal")
    st.info("Sign in with the **email** or **mobile** registered for your client account.")

    login_id = st.text_input("Email or mobile", key="portal_login_id", placeholder="you@client.com or +91…")
    password = st.text_input("Password", type="password", key="portal_login_pass")
    if st.button("Sign in to Client Portal", type="primary", key="portal_login_btn", use_container_width=True):
        user, err = authenticate_portal_user(login_id, password)
        if err:
            st.error(err)
            return
        st.session_state.logged_in = True
        st.session_state.user_role = CLIENT_ROLE
        st.session_state.portal_user_id = user["portal_user_id"]
        st.session_state.client_id = user["client_id"]
        st.session_state.client_name = user.get("client_name") or ""
        st.session_state.user_name = user.get("display_name") or user.get("email") or "Client"
        st.session_state.user_id = user["portal_user_id"]
        st.session_state.username = user.get("email") or user.get("mobile") or ""
        st.session_state.page = "portal_dash"
        st.session_state.last_activity = __import__("time").time()
        st.rerun()
    if st.button("← Back to staff login", key="portal_back_staff"):
        st.session_state.pop("login_portal_mode", None)
        st.rerun()


def render_client_portal_sidebar(user_name: str, logout_fn):
    inject_client_portal_css()
    st.markdown(f"### {ERP_DISPLAY_NAME}")
    st.caption("Client Portal")
    st.markdown(f"**{user_name}**")
    st.caption(st.session_state.get("client_name", ""))
    st.divider()
    current = st.session_state.get("page", "portal_dash")
    for key, label, icon in CLIENT_MENU:
        if st.button(
            f"{icon} {label}",
            key=f"portal_nav_{key}",
            use_container_width=True,
            type="primary" if key == current else "secondary",
        ):
            st.session_state.page = key
            st.rerun()
    st.divider()
    if st.button("Logout", key="portal_logout", use_container_width=True):
        ctx = _portal_context()
        log_portal_audit("logout", portal_user_id=ctx["portal_user_id"], client_id=ctx["client_id"])
        logout_fn()


def _file_download_button(file_path: str, label: str, key: str):
    if not file_path or not os.path.isfile(file_path):
        st.caption(f"{label}: file not available")
        return
    with open(file_path, "rb") as f:
        data = f.read()
    ext = os.path.splitext(file_path)[1].lower() or ".bin"
    mime = "application/pdf" if ext == ".pdf" else "application/octet-stream"
    st.download_button(label, data=data, file_name=os.path.basename(file_path), mime=mime, key=key)


def page_portal_dashboard():
    ctx = _portal_context()
    _audit_view("page", "portal_dash")
    st.subheader("Client Dashboard")
    projects = load_client_projects(ctx["client_id"])
    pending = load_bills_pending_client_review(ctx["client_id"], ctx["client_name"])
    invoices = load_client_invoices(ctx["client_id"], ctx["client_name"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Assigned projects", len(projects))
    c2.metric("Bills awaiting review", len(pending))
    c3.metric("Invoices on file", len(invoices))
    avg_prog = 0.0
    if not projects.empty:
        avg_prog = float(projects["progress_percent"].mean())
    c4.metric("Avg. progress", f"{avg_prog:.1f}%")

    if not pending.empty:
        st.warning(f"You have **{len(pending)}** bill(s) waiting for your approval.")
        if st.button("Review bills now", key="dash_go_bills"):
            st.session_state.page = "portal_bills"
            st.rerun()

    if not projects.empty:
        st.markdown("#### Your projects")
        st.dataframe(
            projects[["project_name", "status", "progress_percent", "location"]],
            use_container_width=True,
            hide_index=True,
        )


def page_portal_projects():
    ctx = _portal_context()
    _audit_view("page", "portal_projects")
    st.subheader("Projects")
    df = load_client_projects(ctx["client_id"])
    if df.empty:
        st.info("No projects are assigned to your account yet. Contact your project manager.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    pick = st.selectbox("View details", [""] + df["project_name"].tolist(), key="portal_proj_pick")
    if not pick:
        return
    row = df[df["project_name"] == pick].iloc[0]
    st.markdown(f"**Progress:** {float(row['progress_percent']):.1f}%")
    st.progress(min(1.0, float(row["progress_percent"]) / 100.0))
    _render_comment_thread("project", row["project_id"], project_id=row["project_id"])


def page_portal_invoices():
    ctx = _portal_context()
    _audit_view("page", "portal_invoices")
    st.subheader("Invoices")
    df = load_client_invoices(ctx["client_id"], ctx["client_name"])
    if df.empty:
        st.info("No invoices found for your assigned projects.")
        return
    st.dataframe(df.drop(columns=["bill_id"], errors="ignore"), use_container_width=True, hide_index=True)
    pick = st.selectbox("Download invoice PDF", [""] + df["bill_no"].tolist(), key="portal_inv_pick")
    if pick:
        bill_id = df[df["bill_no"] == pick].iloc[0]["bill_id"]
        log_portal_audit(
            "download",
            portal_user_id=ctx["portal_user_id"],
            client_id=ctx["client_id"],
            entity_type="invoice",
            entity_id=bill_id,
        )
        try:
            pdf = generate_client_invoice_pdf(bill_id)
            st.download_button(
                "Download PDF",
                data=pdf,
                file_name=f"{pick}.pdf",
                mime="application/pdf",
                key="portal_inv_dl",
            )
        except Exception as exc:
            st.error(str(exc))


def page_portal_bills():
    ctx = _portal_context()
    _audit_view("page", "portal_bills")
    st.subheader("Bills for Approval")
    st.caption("Bill Submitted → Client Review → Approved/Rejected → Accounts Processing")
    df = load_bills_pending_client_review(ctx["client_id"], ctx["client_name"])
    if df.empty:
        st.success("No bills are currently waiting for your review.")
        return
    st.dataframe(df.drop(columns=["bill_id"], errors="ignore"), use_container_width=True, hide_index=True)
    pick = st.selectbox("Review bill", [""] + df["bill_no"].tolist(), key="portal_bill_pick")
    if not pick:
        return
    row = df[df["bill_no"] == pick].iloc[0]
    bill_id = row["bill_id"]
    st.markdown(f"**Amount:** Rs {float(row.get('grand_total') or row['total_amount']):,.2f}")
    comment = st.text_area("Comments (required for rejection)", key="portal_bill_comment")
    c1, c2, c3 = st.columns(3)
    if c1.button("Approve", type="primary", key="portal_bill_approve"):
        ok, msg = approve_client_bill(
            bill_id,
            ctx["client_id"],
            ctx["client_name"],
            portal_user_id=ctx["portal_user_id"],
            display_name=ctx["display_name"],
            comment=comment,
        )
        if ok:
            notify_accounts_bill_decision(bill_id, "approved", ctx["client_name"], comment)
            st.success("Bill approved. Accounts will process payment.")
            st.rerun()
        else:
            st.error(msg)
    if c2.button("Reject", key="portal_bill_reject"):
        ok, msg = reject_client_bill(
            bill_id,
            ctx["client_id"],
            ctx["client_name"],
            portal_user_id=ctx["portal_user_id"],
            display_name=ctx["display_name"],
            comment=comment,
        )
        if ok:
            notify_accounts_bill_decision(bill_id, "rejected", ctx["client_name"], comment)
            st.success("Bill rejected. Your comment was recorded.")
            st.rerun()
        else:
            st.error(msg)
    if c3.button("Download PDF", key="portal_bill_pdf"):
        log_portal_audit(
            "download",
            portal_user_id=ctx["portal_user_id"],
            client_id=ctx["client_id"],
            entity_type="client_bill",
            entity_id=bill_id,
        )
        try:
            pdf = generate_client_invoice_pdf(bill_id)
            st.download_button(
                "Save PDF",
                data=pdf,
                file_name=f"{pick}.pdf",
                mime="application/pdf",
                key="portal_bill_dl",
            )
        except Exception as exc:
            st.error(str(exc))
    _render_comment_thread("client_bill", bill_id)


def page_portal_documents():
    ctx = _portal_context()
    _audit_view("page", "portal_documents")
    st.subheader("Documents & Drawings")
    projects = load_client_projects(ctx["client_id"])
    if projects.empty:
        st.info("No projects assigned.")
        return
    pick = st.selectbox("Project", projects["project_name"].tolist(), key="portal_doc_proj")
    row = projects[projects["project_name"] == pick].iloc[0]
    pid = row["project_id"]
    uploads, drawings = load_project_documents(ctx["client_id"], pid)
    st.markdown("#### Project uploads")
    if uploads.empty:
        st.caption("No uploaded documents.")
    else:
        for _, u in uploads.iterrows():
            log_portal_audit(
                "download",
                portal_user_id=ctx["portal_user_id"],
                client_id=ctx["client_id"],
                entity_type="document",
                entity_id=u["file_path"],
            )
            _file_download_button(u["file_path"], u.get("document_type") or "Document", f"dl_{u.name}")
    st.markdown("#### Drawings & controlled documents")
    if drawings.empty:
        st.caption("No drawings on file.")
    else:
        for _, d in drawings.iterrows():
            _file_download_button(d["file_path"], d.get("doc_title") or "Drawing", f"drw_{d.name}")


def page_portal_progress():
    ctx = _portal_context()
    _audit_view("page", "portal_progress")
    st.subheader("Progress Reports")
    df = load_progress_reports(ctx["client_id"])
    if df.empty:
        st.info("No DPR progress entries for your projects yet.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    projects = load_client_projects(ctx["client_id"])
    if projects.empty:
        return
    pick = st.selectbox("Download progress PDF by project", [""] + projects["project_name"].tolist(), key="portal_prog_pdf")
    if pick:
        row = projects[projects["project_name"] == pick].iloc[0]
        log_portal_audit(
            "download",
            portal_user_id=ctx["portal_user_id"],
            client_id=ctx["client_id"],
            entity_type="progress_report",
            entity_id=row["project_id"],
        )
        try:
            pdf = generate_project_progress_pdf(row["project_id"], row["project_name"])
            st.download_button(
                "Download progress PDF",
                data=pdf,
                file_name=f"progress_{pick}.pdf",
                mime="application/pdf",
                key="portal_prog_dl",
            )
        except Exception as exc:
            st.error(str(exc))


def page_portal_payments():
    ctx = _portal_context()
    _audit_view("page", "portal_payments")
    st.subheader("Payment History")
    receipts, paid_bills = load_payment_history(ctx["client_id"], ctx["client_name"])
    st.markdown("#### Receipts")
    if receipts.empty:
        st.caption("No receipt vouchers recorded.")
    else:
        st.dataframe(receipts, use_container_width=True, hide_index=True)
    st.markdown("#### Paid / approved invoices")
    if paid_bills.empty:
        st.caption("No paid invoices yet.")
    else:
        st.dataframe(paid_bills.drop(columns=["bill_id"], errors="ignore"), use_container_width=True, hide_index=True)


def _render_comment_thread(entity_type: str, entity_id: str, project_id: str = ""):
    ctx = _portal_context()
    st.markdown("#### Comments")
    comments = load_entity_comments(ctx["client_id"], entity_type, entity_id)
    if not comments.empty:
        for _, c in comments.iterrows():
            st.caption(f"{c['created_at']} — {c['body']}")
    new_body = st.text_input("Add a comment", key=f"portal_cmt_{entity_type}_{entity_id}")
    if st.button("Post comment", key=f"portal_cmt_btn_{entity_type}_{entity_id}"):
        _, err = add_client_comment(
            ctx["client_id"],
            entity_type,
            entity_id,
            new_body,
            project_id=project_id,
            portal_user_id=ctx["portal_user_id"],
        )
        if err:
            st.error(err)
        else:
            st.success("Comment posted.")
            st.rerun()


def page_portal_admin_assignments():
    """Internal ERP: assign clients to projects and manage portal users."""
    from modules.roles import is_management, is_project_manager, is_super_admin

    role = st.session_state.get("user_role", "")
    if not (is_super_admin(role) or is_management(role) or is_project_manager(role)):
        st.error("You do not have permission to manage client portal assignments.")
        return

    st.subheader("Client Portal — Project Assignments")
    tab_assign, tab_users = st.tabs(["Project assignments", "Portal users"])

    with tab_assign:
        clients = load_clients_for_admin()
        projects = load_projects_for_assignment()
        if clients.empty:
            st.info("Create clients in CRM first.")
            return
        c1, c2 = st.columns(2)
        client_pick = c1.selectbox(
            "Client",
            clients["client_id"].tolist(),
            format_func=lambda x: clients[clients["client_id"] == x]["client_name"].iloc[0],
            key="adm_client_pick",
        )
        proj_pick = c2.selectbox(
            "Project",
            projects["project_id"].tolist(),
            format_func=lambda x: projects[projects["project_id"] == x]["project_name"].iloc[0],
            key="adm_proj_pick",
        )
        if st.button("Assign project to client", type="primary", key="adm_assign_btn"):
            prow = projects[projects["project_id"] == proj_pick].iloc[0]
            aid, err = assign_client_project(
                client_pick,
                proj_pick,
                prow["project_name"],
                assigned_by=st.session_state.get("user_name", ""),
            )
            if err:
                st.error(err)
            else:
                st.success(f"Assigned ({aid}).")
                st.rerun()
        st.markdown("#### Current assignments")
        assign_df = list_assignments()
        st.dataframe(assign_df, use_container_width=True, hide_index=True)
        if not assign_df.empty:
            rem = st.selectbox("Remove assignment", [""] + assign_df["assignment_id"].tolist(), key="adm_rem_assign")
            if rem and st.button("Remove", key="adm_rem_btn"):
                remove_client_project_assignment(rem, actor=st.session_state.get("user_name", ""))
                st.rerun()

    with tab_users:
        clients = load_clients_for_admin()
        client_for_user = st.selectbox(
            "Client for new portal login",
            clients["client_id"].tolist(),
            format_func=lambda x: clients[clients["client_id"] == x]["client_name"].iloc[0],
            key="adm_portal_client",
        )
        email = st.text_input("Email", key="adm_portal_email")
        mobile = st.text_input("Mobile", key="adm_portal_mobile")
        display = st.text_input("Display name", key="adm_portal_display")
        pwd = st.text_input("Initial password", type="password", key="adm_portal_pwd")
        if st.button("Create portal user", key="adm_create_portal_user"):
            policy_err = validate_password_policy(pwd)
            if policy_err:
                st.error(policy_err)
            else:
                uid, err = create_portal_user(
                    client_for_user,
                    email=email,
                    mobile=mobile,
                    display_name=display,
                    password=pwd,
                    actor=st.session_state.get("user_name", ""),
                )
                if err:
                    st.error(err)
                else:
                    st.success(f"Portal user created: {uid}")
        st.markdown("#### Portal users")
        st.dataframe(list_portal_users(), use_container_width=True, hide_index=True)


def portal_page_handler(page_key: str):
    handlers = {
        "portal_dash": page_portal_dashboard,
        "portal_projects": page_portal_projects,
        "portal_invoices": page_portal_invoices,
        "portal_bills": page_portal_bills,
        "portal_documents": page_portal_documents,
        "portal_progress": page_portal_progress,
        "portal_payments": page_portal_payments,
    }
    fn = handlers.get(page_key)
    if fn:
        fn()
    else:
        st.warning(f"Unknown portal page: {page_label(page_key)}")
