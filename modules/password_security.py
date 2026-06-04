"""Password hashing and verification for MAXEK ERP users."""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    """Return a bcrypt hash string; never store the plain password."""
    if not plain:
        raise ValueError("Password cannot be empty.")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def is_password_hashed(stored: str) -> bool:
    stored = (stored or "").strip()
    return stored.startswith(("$2a$", "$2b$", "$2y$"))


def verify_password(plain: str, stored: str) -> bool:
    """Verify plain password against bcrypt hash or legacy plaintext."""
    if not plain or not stored:
        return False
    stored = stored.strip()
    if is_password_hashed(stored):
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False
    return plain == stored


def password_needs_rehash(stored: str) -> bool:
    """True when login succeeded with legacy plaintext — rehash on next save."""
    return bool(stored) and not is_password_hashed(stored)


def validate_password_policy(password: str) -> str | None:
    """Return an error message when password fails policy, else None."""
    pwd = (password or "").strip()
    if len(pwd) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isupper() for c in pwd):
        return "Password must include an uppercase letter."
    if not any(c.islower() for c in pwd):
        return "Password must include a lowercase letter."
    if not any(c.isdigit() for c in pwd):
        return "Password must include a number."
    return None
