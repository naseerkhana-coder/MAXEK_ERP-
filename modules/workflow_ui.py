"""Reusable Streamlit controls for standard approval workflow transitions."""

from __future__ import annotations

import streamlit as st

from modules.approval_workflow import (
    TRANSITION_ACTION,
    VALID_TRANSITIONS,
    WORKFLOW_STATUSES,
    can_transition,
    load_workflow_audit,
    normalize_status,
    transition,
)
from modules.roles import (
    can_approve_workflow,
    can_check_workflow,
    can_mark_paid_workflow,
    can_prepare_workflow,
    can_release_payment_workflow,
    is_super_admin,
)

_ACTION_LABELS = {
    "prepare": "Submit / Prepare",
    "check": "Check",
    "approve": "Approve",
    "release_payment": "Release Payment",
    "mark_paid": "Mark Paid",
    "return_draft": "Return to Draft",
    "md_return": "MD return",
}

_MD_RETURN_STATUSES = frozenset({"Checked", "Prepared", "Draft"})
_MD_RETURN_LABELS = {
    "Checked": "Send back to Checker",
    "Prepared": "Send back to Maker",
    "Draft": "Send back to Draft",
}


def _session_user_role() -> tuple[str, str, str]:
    return (
        st.session_state.get("user_name", "User"),
        st.session_state.get("user_role", "Admin"),
        st.session_state.get("username", st.session_state.get("user_name", "User")),
    )


def _role_may_transition(role: str, entity_type: str, target_status: str) -> bool:
    action = TRANSITION_ACTION.get(target_status, "")
    if action == "prepare":
        return can_prepare_workflow(role, entity_type)
    if action == "check":
        return can_check_workflow(role, entity_type)
    if action == "approve":
        return can_approve_workflow(role, entity_type)
    if action == "release_payment":
        return can_release_payment_workflow(role)
    if action == "mark_paid":
        return can_mark_paid_workflow(role)
    if action == "return_draft":
        return can_prepare_workflow(role, entity_type) or can_check_workflow(role, entity_type)
    return False


def render_workflow_action_panel(
    entity_type: str,
    entity_id: str,
    current_status: str,
    *,
    key_prefix: str = "wf",
    show_audit: bool = True,
    show_payment_ref: bool = True,
) -> bool:
    """
    Render workflow step buttons for the current record.
    Returns True if a transition was applied (caller may rerun).
    """
    if not entity_id:
        return False

    user, role, username = _session_user_role()
    canon = normalize_status(current_status, entity_type)
    st.markdown("#### Workflow")
    st.caption(f"Current status: **{canon}**")

    if canon in ("Paid", "Rejected", "Cancelled", "Void"):
        if show_audit:
            _render_audit_block(entity_type, entity_id)
        return False

    next_options = VALID_TRANSITIONS.get(canon, ())
    comment = st.text_input("Comments", key=f"{key_prefix}_{entity_id}_comment")
    payment_ref = ""
    if show_payment_ref and any(s in next_options for s in ("Payment Released", "Paid")):
        payment_ref = st.text_input(
            "Payment reference",
            key=f"{key_prefix}_{entity_id}_payref",
            help="Cheque / UPI / bank reference when releasing or marking paid.",
        )

    allowed: list[str] = []
    for target in next_options:
        if not can_transition(canon, target, role=role):
            continue
        if canon == "Approved" and target in _MD_RETURN_STATUSES:
            continue
        if _role_may_transition(role, entity_type, target):
            allowed.append(target)

    changed = False

    if allowed:
        try:
            from modules.workflow_assignments_db import assignment_summary_for_step

            for step in allowed:
                summary = assignment_summary_for_step(entity_type, step)
                if "**" in summary:
                    st.caption(summary)
        except Exception:
            pass

        cols = st.columns(min(len(allowed), 4))
        for idx, target in enumerate(allowed):
            action = TRANSITION_ACTION.get(target, "status_change")
            label = _ACTION_LABELS.get(action, target)
            with cols[idx % len(cols)]:
                if st.button(label, key=f"{key_prefix}_{entity_id}_{target}", width="stretch"):
                    ok, msg = transition(
                        entity_type,
                        entity_id,
                        target,
                        user,
                        role,
                        comment=comment,
                        payment_ref=payment_ref,
                        actor_username=username,
                    )
                    if ok:
                        st.success(msg)
                        changed = True
                    else:
                        st.error(msg)
    elif not (canon == "Approved" and is_super_admin(role)):
        st.info("No workflow actions available for your role at this status.")

    if canon == "Approved" and is_super_admin(role):
        st.markdown("**MD — send back for follow-up**")
        from modules.user_workflow_permissions import list_handlers_for_module
        from modules.workflow_assignments_db import list_active_usernames

        handlers = list_handlers_for_module(entity_type) or list_active_usernames()
        if not handlers:
            st.caption("Assign **Handler** users in Maker–Checker Setup first.")
        else:
            return_to = st.selectbox(
                "Assign follow-up to",
                handlers,
                key=f"{key_prefix}_{entity_id}_return_to",
            )
            md_cols = st.columns(3)
            for idx, target in enumerate(("Checked", "Prepared", "Draft")):
                if target not in next_options:
                    continue
                label = _MD_RETURN_LABELS.get(target, target)
                with md_cols[idx]:
                    if st.button(label, key=f"{key_prefix}_{entity_id}_md_{target}", width="stretch"):
                        ok, msg = transition(
                            entity_type,
                            entity_id,
                            target,
                            user,
                            role,
                            comment=comment,
                            actor_username=username,
                            return_to_username=return_to,
                        )
                        if ok:
                            st.success(msg)
                            changed = True
                        else:
                            st.error(msg)

    if show_audit:
        _render_audit_block(entity_type, entity_id)
    return changed


def render_workflow_status_steps(current_status: str | None = None) -> None:
    """Visual step indicator (Draft → … → Paid)."""
    canon = normalize_status(current_status or "Draft")
    try:
        current_idx = WORKFLOW_STATUSES.index(canon)
    except ValueError:
        current_idx = 0
    parts = []
    for idx, label in enumerate(WORKFLOW_STATUSES):
        if idx < current_idx:
            parts.append(f"✓ {label}")
        elif idx == current_idx:
            parts.append(f"**→ {label}**")
        else:
            parts.append(label)
    st.caption(" · ".join(parts))


def _render_audit_block(entity_type: str, entity_id: str) -> None:
    audit = load_workflow_audit(entity_type, entity_id, limit=15)
    if audit.empty:
        return
    with st.expander("Workflow audit", expanded=False):
        st.dataframe(audit, width="stretch", hide_index=True)
