"""My Profile, Change Password, Security Settings, and preferences."""

from __future__ import annotations

import os

import streamlit as st

from modules.database import BASE_DIR
from modules.roles import display_role_name
from modules.user_account import (
    change_password,
    get_security_summary,
    get_user_by_id,
    save_profile_photo,
    update_user_profile,
    user_must_change_password,
    validate_new_password,
)


def page_account_profile():
    user_id = st.session_state.get("user_id", "")
    if not user_id:
        st.error("Session expired. Please log in again.")
        return

    if user_must_change_password(user_id):
        st.warning(
            "You must change your password before using the rest of the system. "
            "Complete the form in **Change Password** below."
        )

    focus = st.session_state.pop("account_focus", None)
    if focus == "password":
        st.info("Use the **Change Password** tab to update your password.")

    tab_profile, tab_password, tab_security = st.tabs(
        ["My Profile", "Change Password", "Security Settings"]
    )

    with tab_profile:
        _render_profile_tab(user_id)

    with tab_password:
        _render_change_password_tab(user_id)

    with tab_security:
        _render_security_tab(user_id)


def _profile_photo_markup(photo_path: str, name: str) -> str:
    if photo_path:
        abs_path = os.path.join(BASE_DIR, photo_path.replace("/", os.sep))
        if os.path.isfile(abs_path):
            import base64

            ext = os.path.splitext(abs_path)[1].lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
            with open(abs_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            return (
                f'<img src="data:{mime};base64,{b64}" '
                f'style="width:96px;height:96px;border-radius:50%;object-fit:cover;" '
                f'alt="Profile photo" />'
            )
    initial = (name[:1] or "U").upper()
    return (
        f'<div style="width:96px;height:96px;border-radius:50%;background:#1e3a5f;'
        f'color:#fff;display:flex;align-items:center;justify-content:center;'
        f'font-size:2rem;font-weight:700;">{initial}</div>'
    )


def _render_profile_tab(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        st.error("Could not load your profile.")
        return

    st.markdown("### My Profile")
    st.caption(
        "View your account details and update contact information. "
        "Username and role are managed by an administrator."
    )

    st.markdown(_profile_photo_markup(user.get("profile_photo", ""), user["full_name"]), unsafe_allow_html=True)

    with st.form("account_profile_form"):
        c1, c2 = st.columns(2)
        full_name = c1.text_input("Employee Name", value=user["full_name"])
        user_id_display = c2.text_input("User ID", value=user["user_id"], disabled=True)
        designation = c1.text_input("Designation", value=user.get("designation") or "—", disabled=True)
        department = c2.text_input("Department", value=user.get("department") or "—", disabled=True)
        mobile = c1.text_input("Mobile Number", value=user["mobile"])
        email = c2.text_input("Email Address", value=user["email"])
        username = st.text_input("Username", value=user["username"], disabled=True)
        role = st.text_input("Role", value=display_role_name(user["role"]), disabled=True)
        photo_upload = st.file_uploader(
            "Profile Photo",
            type=["jpg", "jpeg", "png"],
            help="Optional. JPG or PNG, max one file.",
        )

        if st.form_submit_button("Save preferences", type="primary", width="stretch"):
            photo_path = None
            if photo_upload is not None:
                saved, err = save_profile_photo(user_id, photo_upload)
                if err:
                    st.error(err)
                    return
                photo_path = saved
            ok, msg = update_user_profile(
                user_id,
                full_name=full_name,
                mobile=mobile,
                email=email,
                profile_photo=photo_path,
                actor=user_id,
            )
            if ok:
                st.session_state.user_name = full_name.strip()
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


def _render_change_password_tab(user_id: str):
    st.markdown("### Change Password")
    st.caption(
        "Enter your current password, then choose a new password "
        "(at least 8 characters with upper, lower, and a number)."
    )

    with st.form("account_change_password_form"):
        current = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password", type="password")
        confirm = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Update password", type="primary", width="stretch"):
            err = validate_new_password(new_pwd, confirm)
            if err:
                st.error(err)
            else:
                ok, msg = change_password(user_id, current, new_pwd, actor=user_id)
                if ok:
                    st.session_state.pop("account_focus", None)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)


def _render_security_tab(user_id: str):
    st.markdown("### Security Settings")
    summary = get_security_summary(
        user_id,
        session_username=st.session_state.get("username", ""),
    )
    import time
    from modules.database import _finance_setting

    try:
        minutes = int(_finance_setting("session_timeout_minutes", "480") or 480)
    except ValueError:
        minutes = 480
    session_started = st.session_state.get("last_activity", time.time())
    started_label = time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(session_started))

    c1, c2 = st.columns(2)
    c1.metric("Last Login Date & Time", summary.get("last_login_at") or "—")
    c2.metric("Last Password Change", summary.get("password_changed_at") or "—")
    st.markdown("#### Active session")
    st.write(f"**Signed in as:** {summary.get('username') or '—'}")
    st.write(f"**Session started:** {started_label}")
    st.write(f"**Timeout:** {max(15, minutes)} minutes of inactivity")
