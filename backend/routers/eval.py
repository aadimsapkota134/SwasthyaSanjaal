"""NepClinBench evaluation API router for SwasthyaSanjaal.

Provides endpoints to trigger live benchmark evaluations, retrieve historical
runs from SQLite, and inspect detailed performance breakdowns across Devanagari,
Romanized, Code-Mixed, Negation, and OCR-corrupted test cases.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.auth.router import require_auth
from backend.db import session as db_session
from backend.eval.bench import (
    ItemResult,
    RunSummary,
    caveats,
    list_runs,
    load_items,
    persist,
    read_run,
    run_benchmark,
)
from backend.nlp.lexicon import get_lexicon
from backend.nlp.tier3 import GemmaTier3Matcher

router = APIRouter(prefix="/eval", tags=["evaluation"])


class EvalRunRequest(BaseModel):
    use_model: bool = Field(
        default=False,
        description="Enable Tier 3 Gemma model candidate selection (defaults to False for deterministic proof)",
    )
    persist: bool = Field(
        default=True,
        description="Persist item evaluation results into SQLite eval_results table",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description="Optional limit for smoke testing subsets of the benchmark",
    )


class CategoryRow(BaseModel):
    category: str
    total: int
    exact: int
    accuracy: float


class ItemRow(BaseModel):
    item_id: int
    category: str
    derivation: str
    input: str
    gold_present: list[str]
    gold_negated: list[str]
    predicted_present: list[str]
    predicted_negated: list[str]
    tier_fired: int | None
    correct: bool
    missed: list[str]
    spurious: list[str]

    @classmethod
    def from_result(cls, entry: ItemResult) -> ItemRow:
        return cls(
            item_id=entry.item_id,
            category=entry.category,
            derivation=entry.derivation,
            input=entry.input,
            gold_present=entry.gold_present,
            gold_negated=entry.gold_negated,
            predicted_present=entry.predicted_present,
            predicted_negated=entry.predicted_negated,
            tier_fired=entry.tier_fired,
            correct=entry.correct,
            missed=entry.missed,
            spurious=entry.spurious,
        )


class EvalRunResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    run_id: str
    created_at: str
    use_model: bool
    persisted: bool
    total: int
    exact: int
    accuracy: float
    negation_total: int
    negation_correct: int
    duration_total: int
    duration_correct: int
    precision: float
    recall: float
    f1: float
    tier_counts: dict[int, int]
    tier_precision: dict[int, float | None]
    model_share: float
    by_category: list[CategoryRow]
    brand_items: int
    brand_resolved: int
    derivation_counts: dict[str, int]
    caveats: list[str]
    items: list[ItemRow]

    @classmethod
    def from_summary(cls, summary: RunSummary, *, persisted: bool) -> EvalRunResponse:
        return cls(
            run_id=summary.run_id,
            created_at=summary.created_at,
            use_model=summary.use_model,
            persisted=persisted,
            total=summary.total,
            exact=summary.exact,
            accuracy=round(summary.accuracy, 4),
            negation_total=summary.negation_total,
            negation_correct=summary.negation_correct,
            duration_total=summary.duration_total,
            duration_correct=summary.duration_correct,
            precision=round(summary.precision, 4),
            recall=round(summary.recall, 4),
            f1=round(summary.f1, 4),
            tier_counts=summary.tier_counts,
            tier_precision={
                tier: (round(val, 4) if val is not None else None)
                for tier, val in summary.tier_precision.items()
            },
            model_share=round(summary.model_share, 4),
            by_category=[
                CategoryRow(
                    category=c.category,
                    total=c.total,
                    exact=c.exact,
                    accuracy=round(c.accuracy, 4),
                )
                for c in summary.by_category
            ],
            brand_items=summary.brand_items,
            brand_resolved=summary.brand_resolved,
            derivation_counts=summary.derivation_counts,
            caveats=caveats(summary),
            items=[ItemRow.from_result(entry) for entry in summary.items],
        )


class RunListRow(BaseModel):
    run_id: str
    created_at: str
    total: int
    exact: int


@router.post("/run", response_model=EvalRunResponse)
def execute_eval(
    payload: EvalRunRequest | None = None,
    current_user: dict = Depends(require_auth),
) -> EvalRunResponse:
    """Executes live NepClinBench evaluation against active clinical lexicon."""
    request = payload or EvalRunRequest()
    items = load_items()
    if request.limit is not None:
        items = items[: request.limit]

    tier3 = GemmaTier3Matcher() if request.use_model else None
    summary = run_benchmark(lexicon=get_lexicon(), tier3=tier3, items=items)

    should_persist = request.persist and request.limit is None
    if should_persist:
        with db_session() as con:
            persist(summary, con)

    return EvalRunResponse.from_summary(summary, persisted=should_persist)


@router.get("/latest", response_model=EvalRunResponse)
def get_latest_eval(
    current_user: dict = Depends(require_auth),
) -> EvalRunResponse:
    """Returns the latest evaluation report, computing it on demand if no prior runs exist."""
    summary = run_benchmark(lexicon=get_lexicon())
    return EvalRunResponse.from_summary(summary, persisted=False)


@router.get("/runs", response_model=list[RunListRow])
def get_historical_runs(
    current_user: dict = Depends(require_auth),
) -> list[RunListRow]:
    """Lists historical benchmark runs stored in database."""
    with db_session() as con:
        return [RunListRow(**row) for row in list_runs(con)]


@router.get("/runs/{run_id}")
def get_run_details(
    run_id: str,
    current_user: dict = Depends(require_auth),
) -> dict[str, Any]:
    """Retrieves all stored item predictions for a historical evaluation run."""
    with db_session() as con:
        rows = read_run(run_id, con)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found")
    return {"run_id": run_id, "rows": rows}
