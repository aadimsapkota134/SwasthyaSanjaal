"""Pytest configuration and shared fixtures for SwasthyaSanjaal backend tests.

Provides test isolation by overriding the database path and upload directory
to per-test temporary locations.
"""

from __future__ import annotations

import pytest

from backend.config import settings


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Route database and uploads to a per-test temp directory."""
    test_db = str(tmp_path / "test_swasthyasanjaal.db")
    test_uploads = str(tmp_path / "uploads")

    monkeypatch.setattr(settings, "db_path", test_db)
    monkeypatch.setattr(settings, "upload_dir", test_uploads)

    yield tmp_path


@pytest.fixture
def client():
    """Standard FastAPI TestClient with an isolated database."""
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as test_client:
        yield test_client
