"""NepClinBench evaluation runner and API endpoint tests for SwasthyaSanjaal."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.db import init_db, session
from backend.eval.bench import run_benchmark
from backend.nlp.lexicon import Lexicon, get_lexicon
from backend.nlp.normalize import normalize
from backend.main import app
from backend.seed import seed_all, bootstrap_admin


@pytest.fixture(scope="function")
def lexicon() -> Lexicon:
    init_db()
    with session() as con:
        seed_all(con)
        bootstrap_admin(con, "admin@swasthya.example", "AdminPass123!")
    return get_lexicon()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_client() -> TestClient:
    with TestClient(app) as test_client:
        # Bootstrap admin
        init_db()
        with session() as con:
            seed_all(con)
            bootstrap_admin(con, "admin@swasthya.example", "AdminPass123!")
        # Login
        resp = test_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@swasthya.example", "password": "AdminPass123!"},
        )
        assert resp.status_code == 200
        yield test_client


def test_runner_reproduces_the_documented_result(lexicon: Lexicon) -> None:
    """Recomputes NepClinBench gold numbers: 58/60 exact match, 10/10 negation, 2/2 duration."""
    summary = run_benchmark(lexicon=lexicon)

    assert summary.total == 60
    assert summary.exact == 58
    assert summary.accuracy == pytest.approx(58 / 60, abs=1e-3)
    assert summary.precision == 1.0  # Zero hallucination
    assert summary.negation_correct == summary.negation_total == 10
    assert summary.duration_correct == summary.duration_total == 2


def test_the_only_two_failures_are_the_two_disputed_labels(lexicon: Lexicon) -> None:
    """Items 39 and 40 are recorded as contested code-mixed labels."""
    summary = run_benchmark(lexicon=lexicon)
    assert sorted(e.item_id for e in summary.items if not e.correct) == [39, 40]


def test_the_reported_run_uses_no_model(lexicon: Lexicon) -> None:
    """Validates that all reported matches came from deterministic tiers 1 and 2."""
    summary = run_benchmark(lexicon=lexicon)
    tier3_count = summary.tier_counts.get(3, 0)
    assert tier3_count == 0


def test_eval_latest_endpoint(admin_client) -> None:
    resp = admin_client.get("/api/v1/eval/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "exact" in data
    assert "accuracy" in data


def test_eval_run_endpoint_persists_to_db(admin_client) -> None:
    resp = admin_client.post(
        "/api/v1/eval/run",
        json={"use_model": False, "persist": True, "limit": 10},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert data["persisted"] is True


def test_eval_run_endpoint_requires_auth(client) -> None:
    resp = client.get("/api/v1/eval/latest")
    assert resp.status_code == 401
