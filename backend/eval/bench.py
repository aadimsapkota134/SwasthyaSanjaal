"""NepClinBench evaluation runner and scoring engine for SwasthyaSanjaal.

Scores clinical concept extraction, negation accuracy, duration detection,
and brand-to-generic drug resolution across the 60 gold benchmark items.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.nlp.lexicon import Lexicon, get_lexicon
from backend.nlp.normalize import NormalizationResult, normalize
from backend.nlp.tier3 import Tier3Matcher

CATEGORIES = (
    "clean_devanagari",
    "romanized",
    "code_mixed",
    "negation",
    "ocr_corrupted",
)


@dataclass(slots=True)
class ItemResult:
    """One benchmark item, scored."""
    item_id: int
    category: str
    derivation: str
    input: str
    gold_present: list[str]
    gold_negated: list[str]
    predicted_present: list[str]
    predicted_negated: list[str]
    tiers: list[int]
    correct: bool
    negation_correct: bool
    missed: list[str]
    spurious: list[str]
    gold_duration_days: int | None = None
    predicted_duration_days: int | None = None

    @property
    def tier_fired(self) -> int | None:
        return max(self.tiers) if self.tiers else None


@dataclass(slots=True)
class CategoryScore:
    category: str
    total: int = 0
    exact: int = 0

    @property
    def accuracy(self) -> float:
        return self.exact / self.total if self.total else 0.0


@dataclass(slots=True)
class RunSummary:
    run_id: str
    created_at: str
    use_model: bool
    total: int
    exact: int
    negation_total: int
    negation_correct: int
    duration_total: int
    duration_correct: int
    true_positives: int
    false_positives: int
    false_negatives: int
    tier_counts: dict[int, int]
    tier_precision: dict[int, float | None]
    by_category: list[CategoryScore]
    brand_items: int
    brand_resolved: int
    derivation_counts: dict[str, int]
    configuration: str = "system"
    out_of_vocabulary: list[str] = field(default_factory=list)
    unanswered: int = 0
    items: list[ItemResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.exact / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0

    @property
    def model_share(self) -> float:
        matches = sum(self.tier_counts.values())
        return self.tier_counts.get(3, 0) / matches if matches else 0.0


def load_items(path: str | Path | None = None) -> list[dict]:
    candidate_paths = [
        Path(path) if path else None,
        Path(settings.benchmark_path),
        Path(__file__).resolve().parent.parent.parent / "data" / "nepclinbench.json",
        Path("data/nepclinbench.json"),
    ]
    for p in candidate_paths:
        if p and p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("Could not locate nepclinbench.json")


def _present(result: NormalizationResult) -> set[str]:
    return {m.concept.concept_id for m in result.assertions if not m.negated}


def _negated(result: NormalizationResult) -> set[str]:
    return {m.concept.concept_id for m in result.assertions if m.negated}


def _score_item(item: dict, result: NormalizationResult) -> ItemResult:
    gold_present = set(item["gold_concepts"])
    gold_negated = set(item.get("gold_negated", []))
    predicted_present = _present(result)
    predicted_negated = _negated(result)

    correct = predicted_present == gold_present and predicted_negated == gold_negated
    gold_all = gold_present | gold_negated
    predicted_all = predicted_present | predicted_negated
    duration_gold = item.get("gold_duration_days")

    return ItemResult(
        item_id=item["id"],
        category=item["category"],
        derivation=item.get("derivation", "unknown"),
        input=item["input"],
        gold_present=sorted(gold_present),
        gold_negated=sorted(gold_negated),
        predicted_present=sorted(predicted_present),
        predicted_negated=sorted(predicted_negated),
        tiers=[m.tier for m in result.assertions],
        correct=correct,
        negation_correct=predicted_negated == gold_negated,
        missed=sorted(gold_all - predicted_all),
        spurious=sorted(predicted_all - gold_all),
        gold_duration_days=duration_gold,
        predicted_duration_days=result.duration_days,
    )


def _brand_resolution(item: ItemResult, lexicon: Lexicon) -> tuple[bool, bool]:
    exercises = False
    resolved = True
    for concept_id in item.gold_present + item.gold_negated:
        concept = lexicon.concepts.get(concept_id)
        if concept is None or concept.concept_type != "drug_brand":
            continue
        exercises = True
        if concept.generic_of is None:
            resolved = False
        elif concept_id not in item.predicted_present + item.predicted_negated:
            resolved = False
    return exercises, resolved


def _predictor(lexicon: Lexicon, tier3: Tier3Matcher | None, baseline: object | None):
    if baseline is None:
        def predict(text: str):
            return normalize(text, lexicon=lexicon, tier3=tier3), {}
        return predict

    from backend.eval.baseline import as_result

    def predict_baseline(text: str):
        prediction = baseline.extract(text)  # type: ignore[attr-defined]
        return (
            as_result(text, prediction, lexicon),
            {
                "out_of_vocabulary": prediction.out_of_vocabulary,
                "answered": prediction.answered,
            },
        )
    return predict_baseline


def run_benchmark(
    *,
    lexicon: Lexicon | None = None,
    tier3: Tier3Matcher | None = None,
    items: list[dict] | None = None,
    run_id: str | None = None,
    baseline: object | None = None,
) -> RunSummary:
    """Scores NepClinBench against SwasthyaSanjaal normalization or ablation baseline."""
    lexicon = lexicon or get_lexicon()
    items = items if items is not None else load_items()
    predict = _predictor(lexicon, tier3, baseline)

    scored: list[ItemResult] = []
    oov: list[str] = []
    unanswered = 0
    tier_counts: Counter[int] = Counter({1: 0, 2: 0, 3: 0})
    tier_hits: Counter[int] = Counter()
    true_positives = false_positives = false_negatives = 0
    brand_items = brand_resolved = 0

    for item in items:
        result, extra = predict(item["input"])
        oov.extend(extra.get("out_of_vocabulary", ()))
        unanswered += int(not extra.get("answered", True))
        entry = _score_item(item, result)
        scored.append(entry)

        gold_all = set(entry.gold_present) | set(entry.gold_negated)
        predicted_all = set(entry.predicted_present) | set(entry.predicted_negated)
        true_positives += len(predicted_all & gold_all)
        false_positives += len(predicted_all - gold_all)
        false_negatives += len(gold_all - predicted_all)

        for match in result.assertions:
            tier_counts[match.tier] += 1
            if match.concept.concept_id in gold_all:
                tier_hits[match.tier] += 1

        exercises, ok = _brand_resolution(entry, lexicon)
        if exercises:
            brand_items += 1
            brand_resolved += ok

    by_category = {name: CategoryScore(name) for name in CATEGORIES}
    for entry in scored:
        bucket = by_category.setdefault(entry.category, CategoryScore(entry.category))
        bucket.total += 1
        bucket.exact += entry.correct

    negation_items = [e for e in scored if e.category == "negation"]
    duration_items = [e for e in scored if e.gold_duration_days is not None]

    return RunSummary(
        run_id=run_id or f"run_{uuid.uuid4().hex[:12]}",
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        use_model=tier3 is not None or baseline is not None,
        total=len(scored),
        exact=sum(e.correct for e in scored),
        negation_total=len(negation_items),
        negation_correct=sum(e.negation_correct for e in negation_items),
        duration_total=len(duration_items),
        duration_correct=sum(
            e.predicted_duration_days == e.gold_duration_days for e in duration_items
        ),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        tier_counts=dict(tier_counts),
        tier_precision={
            tier: (tier_hits[tier] / tier_counts[tier] if tier_counts[tier] else None)
            for tier in (1, 2, 3)
        },
        by_category=[by_category[name] for name in CATEGORIES if name in by_category],
        brand_items=brand_items,
        brand_resolved=brand_resolved,
        derivation_counts=dict(Counter(e.derivation for e in scored)),
        configuration="raw_gemma" if baseline is not None else "system",
        out_of_vocabulary=oov,
        unanswered=unanswered,
        items=scored,
    )


def caveats(summary: RunSummary) -> list[str]:
    notes: list[str] = []
    synthetic = summary.derivation_counts.get("synthetic_perturbation", 0)
    if synthetic:
        notes.append(
            f"{synthetic} OCR-corrupted items were perturbed for benchmarking robustness."
        )
    if summary.configuration == "raw_gemma":
        notes.append(
            "Unconstrained baseline: Gemma 4 with no lexicon, mapped back at 0.80 fuzzy ratio."
        )
        if summary.unanswered:
            notes.append(
                f"{summary.unanswered} item(s) could not reach model endpoint."
            )
    elif summary.tier_counts.get(3, 0) == 0:
        notes.append(
            "Tier 3 never fired: 100% of matches are deterministic dictionary/orthography lookups."
        )
    return notes


def persist(summary: RunSummary, con: sqlite3.Connection) -> None:
    """Inserts item rows into eval_results table."""
    con.executemany(
        """
        INSERT INTO eval_results
            (run_id, item_id, category, tier_fired, correct, predicted, gold, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                summary.run_id,
                str(entry.item_id),
                entry.category,
                entry.tier_fired,
                int(entry.correct),
                json.dumps(
                    {"present": entry.predicted_present, "negated": entry.predicted_negated},
                    ensure_ascii=False,
                ),
                json.dumps(
                    {"present": entry.gold_present, "negated": entry.gold_negated},
                    ensure_ascii=False,
                ),
                summary.created_at,
            )
            for entry in summary.items
        ],
    )


def list_runs(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute(
        """
        SELECT run_id,
               MIN(created_at) AS created_at,
               COUNT(*)        AS total,
               SUM(correct)    AS exact
        FROM eval_results
        GROUP BY run_id
        ORDER BY created_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def read_run(run_id: str, con: sqlite3.Connection) -> list[dict]:
    rows = con.execute(
        "SELECT * FROM eval_results WHERE run_id = ? ORDER BY CAST(item_id AS INTEGER)",
        (run_id,),
    ).fetchall()
    return [dict(row) for row in rows]
