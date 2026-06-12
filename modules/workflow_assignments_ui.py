"""Settings UI — assign Maker / Checker / Approver / Handler modules per user."""

from __future__ import annotations

import streamlit as st

from modules.roles import can_manage_users
from modules.user_workflow_permissions import (
    CAPABILITY_CHECKER,
    CAPABILITY_HANDLER,
    CAPABILITY_MAKER,
    CAPABILITY_APPROVER,
    CAPABILITY_LABELS,
    CONFIGURABLE_MODULES,
    add_modules_for_capability,
    clear_capability_permissions,
    list_users_for_permissions,
    load_permissions_matrix,
    load_user_permissions,
    remove_modules_for_capability,
    save_user_permissions,
)

def _mod_label(module_key: str) -> str:
    return CONFIGURABLE_MODULES.get(module_key, module_key)


def render_create_user_module_permissions(key_prefix: str = "new_user") -> dict[str, list[str]]:
    """Multiselects for user-creation form. Call inside ``st.form`` before submit."""
    options = list(CONFIGURABLE_MODULES.keys())
    st.markdown("#### Module permissions")
    st.caption(
        "Optional — assign which modules this user may use as Maker, Checker, "
        "Approver, or Handler. You can change these later on this page or in Maker–Checker Setup."
    )
    c1, c2 = st.columns(2)
    with c1:
        maker = st.multiselect(
            "Maker — create & submit",
            options,
            format_func=_mod_label,
            key=f"{key_prefix}_maker",
        )
        checker = st.multiselect(
            "Checker — verify",
            options,
            format_func=_mod_label,
            key=f"{key_prefix}_checker",
        )
    with c2:
        approver = st.multiselect(
            "Approver — final sign-off (MD)",
            options,
            format_func=_mod_label,
            key=f"{key_prefix}_approver",
        )
        handler = st.multiselect(
            "Handler — MD follow-up / site / accounts",
            options,
            format_func=_mod_label,
            key=f"{key_prefix}_handler",
        )
    return {
        CAPABILITY_MAKER: maker,
        CAPABILITY_CHECKER: checker,
        CAPABILITY_APPROVER: approver,
        CAPABILITY_HANDLER: handler,
    }


def render_user_module_permissions_editor(user: dict, *, actor: str) -> None:
    """Add / remove module permissions for an existing user."""
    perms = load_user_permissions(user["user_id"])
    st.caption(
        "Add or remove modules for **Maker** and **Checker**. "
        "Changes apply immediately — no need to recreate the user."
    )
    _render_role_editor(user, CAPABILITY_MAKER, perms[CAPABILITY_MAKER], actor=actor)
    st.divider()
    _render_role_editor(user, CAPABILITY_CHECKER, perms[CAPABILITY_CHECKER], actor=actor)
    with st.expander("Approver & Handler (optional)", expanded=False):
        _render_role_editor(user, CAPABILITY_APPROVER, perms[CAPABILITY_APPROVER], actor=actor)
        st.divider()
        _render_role_editor(user, CAPABILITY_HANDLER, perms[CAPABILITY_HANDLER], actor=actor)


def _render_current_modules(modules: list[str]) -> None:
    if not modules:
        st.caption("None assigned yet.")
        return
    st.markdown(
        " · ".join(f"**{_mod_label(m)}**" for m in modules),
    )


def _render_role_editor(
    user: dict,
    capability: str,
    current: list[str],
    *,
    actor: str,
) -> None:
    label = CAPABILITY_LABELS[capability]
    uid = user["user_id"]
    st.markdown(f"#### {label}")
    st.caption("Current modules:")
    _render_current_modules(current)

    available_add = [m for m in CONFIGURABLE_MODULES if m not in current]
    c_add, c_remove = st.columns(2)

    with c_add:
        st.markdown("**Add module(s)**")
        to_add = st.multiselect(
            "Choose modules to add",
            available_add,
            format_func=_mod_label,
            key=f"wf_add_{capability}_{uid}",
            label_visibility="collapsed",
        )
        if st.button(
            f"Add to {label.split('(')[0].strip()}",
            key=f"wf_add_btn_{capability}_{uid}",
            disabled=not to_add,
            width="stretch",
        ):
            ok, msg = add_modules_for_capability(
                uid,
                user["username"],
                capability,
                to_add,
                actor=actor,
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with c_remove:
        st.markdown("**Remove module(s)**")
        to_remove = st.multiselect(
            "Choose modules to remove",
            current,
            format_func=_mod_label,
            key=f"wf_rm_{capability}_{uid}",
            label_visibility="collapsed",
        )
        if st.button(
            f"Remove from {label.split('(')[0].strip()}",
            key=f"wf_rm_btn_{capability}_{uid}",
            disabled=not to_remove,
            width="stretch",
        ):
            ok, msg = remove_modules_for_capability(uid, capability, to_remove)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    if current and st.button(
        f"Clear all {label.split('(')[0].strip()} permissions",
        key=f"wf_clear_{capability}_{uid}",
        type="secondary",
    ):
        ok, msg = clear_capability_permissions(uid, capability)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)


def page_workflow_assignments() -> None:
    st.subheader("Maker–Checker Setup")
    role = st.session_state.get("user_role", "Admin")
    if not can_manage_users(role):
        st.error("Only Super Admin / MD can configure workflow permissions.")
        return

    st.markdown(
        """
Create users under **Settings → Users**, then assign **which modules** each person may
handle as **Maker**, **Checker**, **Handler**, or **Approver**.

Use **Edit permissions** to **add or remove** modules later for staff who already have access.
        """
    )

    users = list_users_for_permissions()
    if not users:
        st.warning("Create users first under **Settings → Users**.")
        return

    tab_edit, tab_bulk, tab_matrix = st.tabs(
        ["Edit permissions (add / remove)", "Replace all at once", "All users overview"]
    )

    labels = {u["label"]: u for u in users}
    actor = st.session_state.get("user_name", "Admin")

    with tab_edit:
        pick_label = st.selectbox(
            "Select user to edit",
            list(labels.keys()),
            key="wf_edit_user_pick",
        )
        user = labels[pick_label]
        perms = load_user_permissions(user["user_id"])

        st.markdown(
            f"### Edit **{user['full_name']}** (`{user['username']}`) — ERP role: {user['role']}"
        )
        st.info(
            "Staff already set as **Maker** or **Checker** can get **more modules** or "
            "**some modules removed** here without recreating the user."
        )

        st.markdown("##### Maker & Checker (most common)")
        _render_role_editor(user, CAPABILITY_MAKER, perms[CAPABILITY_MAKER], actor=actor)
        st.divider()
        _render_role_editor(user, CAPABILITY_CHECKER, perms[CAPABILITY_CHECKER], actor=actor)

        with st.expander("Approver & Handler (optional)", expanded=False):
            _render_role_editor(
                user, CAPABILITY_APPROVER, perms[CAPABILITY_APPROVER], actor=actor
            )
            st.divider()
            _render_role_editor(
                user, CAPABILITY_HANDLER, perms[CAPABILITY_HANDLER], actor=actor
            )

    with tab_bulk:
        pick_label_bulk = st.selectbox(
            "Select user",
            list(labels.keys()),
            key="wf_bulk_user_pick",
        )
        user_bulk = labels[pick_label_bulk]
        perms_bulk = load_user_permissions(user_bulk["user_id"])

        st.caption(
            "Replace the full permission set in one save. "
            "Untick a module in multiselect to remove it from that role."
        )

        options = list(CONFIGURABLE_MODULES.keys())
        fmt = _mod_label

        with st.form("user_wf_perm_bulk_form"):
            maker = st.multiselect(
                "Maker modules — create & submit",
                options,
                default=perms_bulk[CAPABILITY_MAKER],
                format_func=fmt,
            )
            checker = st.multiselect(
                "Checker modules — verify",
                options,
                default=perms_bulk[CAPABILITY_CHECKER],
                format_func=fmt,
            )
            approver = st.multiselect(
                "Approver modules — final approval",
                options,
                default=perms_bulk[CAPABILITY_APPROVER],
                format_func=fmt,
            )
            handler = st.multiselect(
                "Handler modules — MD follow-up",
                options,
                default=perms_bulk[CAPABILITY_HANDLER],
                format_func=fmt,
            )
            submitted = st.form_submit_button("Save all permissions", type="primary")

        if submitted:
            ok, msg = save_user_permissions(
                user_bulk["user_id"],
                user_bulk["username"],
                maker_modules=maker,
                checker_modules=checker,
                approver_modules=approver,
                handler_modules=handler,
                actor=actor,
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with tab_matrix:
        matrix = load_permissions_matrix()
        if matrix.empty:
            st.info("No module permissions saved yet.")
        else:
            filter_user = st.text_input("Filter by name or username")
            show = matrix.copy()
            if filter_user.strip():
                q = filter_user.strip().lower()
                show = show[
                    show["full_name"].astype(str).str.lower().str.contains(q, na=False)
                    | show["username"].astype(str).str.lower().str.contains(q, na=False)
                ]
            cols = [
                c
                for c in (
                    "full_name",
                    "username",
                    "module",
                    "access",
                    "assigned_by",
                    "assigned_at",
                )
                if c in show.columns
            ]
            st.dataframe(show[cols], width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("### Example")
    st.markdown(
        """
| User | Maker | Checker | Handler |
|------|-------|---------|---------|
| Site engineer | Petty Cash, DPR, Timesheet | — | Petty Cash |
| Accounts | — | Petty Cash, Payment Voucher | Payment Voucher |

*Later:* add **Timesheet** as Checker for Accounts, or remove **DPR** from Site engineer — use **Edit permissions**.
        """
    )
