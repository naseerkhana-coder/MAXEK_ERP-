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
)

_ACTION_LABELS = {
    "prepare": "Submit / Prepare",
    "check": "Check",
    "approve": "Approve",
    "release_payment": "Release Payment",
    "mark_paid": "Mark Paid",
    "return_draft": "Return to Draft",
}


def _session_user_role() -> tuple[str, str]:
    return (
        st.session_state.get("user_name", "User"),
        st.session_state.get("user_role", "Admin"),
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

    user, role = _session_user_role()
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

    allowed = [
        s
        for s in next_options
        if can_transition(canon, s) and _role_may_transition(role, entity_type, s)
    ]
    if not allowed:
        st.info("No workflow actions available for your role at this status.")
        if show_audit:
            _render_audit_block(entity_type, entity_id)
        return False

    cols = st.columns(min(len(allowed), 4))
    changed = False
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
