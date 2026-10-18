"""NepClinBench evaluation runner and API endpoint tests for SwasthyaSanjaal."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.db import init_db, session
from backend.eval.bench import run_benchmark
from backend.nlp.lexicon import Lexicon, get_lexicon
from backend.nlp.normalize import normalize
from backend.main import app
from backend.seed import seed_all


@pytest.fixture(scope="function")
def lexicon() -> Lexicon:
    init_db()
    with session() as con:
        seed_all(con)
    return get_lexicon()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
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
    assert summary.tier_counts.get(3, 0) == 0
    assert summary.model_share == 0.0
    assert summary.use_model is False


def test_a_wrong_negation_flag_is_not_a_hit(lexicon: Lexicon) -> None:
    """Verifies that finding a concept with an inverted negation flag scores 0."""
    item = {
        "id": 900,
        "input": "ज्वरो छैन",
        "gold_concepts": [],
        "gold_negated": ["NCL-0001"],
        "category": "negation",
        "derivation": "authored",
    }
    inverted = dict(item, gold_concepts=["NCL-0001"], gold_negated=[])

    assert run_benchmark(lexicon=lexicon, items=[item]).exact == 1
    assert run_benchmark(lexicon=lexicon, items=[inverted]).exact == 0


def test_modifiers_are_not_candidate_answers(lexicon: Lexicon) -> None:
    """Verifies that duration and modifier tokens do not falsely count as clinical findings."""
    result = normalize("ज्वरो, ३ दिन देखि", lexicon=lexicon)
    assert len(result.matches) > len(result.assertions)

    summary = run_benchmark(
        lexicon=lexicon,
        items=[
            {
                "id": 901,
                "input": "ज्वरो, ३ दिन देखि",
                "gold_concepts": ["NCL-0001"],
                "gold_negated": [],
                "gold_duration_days": 3,
                "category": "clean_devanagari",
                "derivation": "authored",
            }
        ],
    )
    assert summary.exact == 1
    assert summary.items[0].spurious == []


def test_eval_latest_endpoint(client: TestClient) -> None:
    """GET /api/v1/eval/latest returns 200 with the 58/60 benchmark report."""
    response = client.get("/api/v1/eval/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 60
    assert data["exact"] == 58
    assert data["precision"] == 1.0
    assert data["negation_correct"] == 10


def test_eval_run_endpoint_persists_to_db(client: TestClient) -> None:
    """POST /api/v1/eval/run executes benchmark and writes to eval_results table."""
    response = client.post("/api/v1/eval/run", json={"use_model": False, "persist": True})
    assert response.status_code == 200
    data = response.json()
    run_id = data["run_id"]
    assert data["total"] == 60
    assert data["exact"] == 58
    assert data["persisted"] is True

    runs_res = client.get("/api/v1/eval/runs")
    assert runs_res.status_code == 200
    run_list = runs_res.json()
    assert any(r["run_id"] == run_id for r in run_list)

    detail_res = client.get(f"/api/v1/eval/runs/{run_id}")
    assert detail_res.status_code == 200
    assert len(detail_res.json()["rows"]) == 60
