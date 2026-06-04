"""Shared pytest fixtures for MAXEK ERP."""

import os
import tempfile

import pytest

from modules import database as db


@pytest.fixture
def tmp_db(monkeypatch):
    """Isolated SQLite database for integration tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass
