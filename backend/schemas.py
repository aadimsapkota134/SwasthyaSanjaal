"""Pydantic v2 schemas for SwasthyaSanjaal API contracts.

These models define data transfer contracts across ingestion, 3-tier normalization,
field-level uncertainty & confirmation, patient health records, clinical standards (FHIR/QR),
and NepClinBench evaluation benchmarks.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# ==============================================================================
# 1. Normalization, Provenance, & Uncertainty Contracts
# ==============================================================================

class GenericRef(BaseModel):
    """Reference to active pharmaceutical ingredient / generic compound."""
    concept_id: str
    canonical_en: str
    canonical_np: str


class NormalizedConcept(BaseModel):
    """Normalized clinical finding, condition, symptom, or medication with provenance and uncertainty."""
    concept_id: str
    surface_form: str = Field(description="Exact span as it appeared in source text")
    canonical_en: str
    canonical_np: str
    concept_type: str = Field(description="condition | symptom | drug_generic | drug_brand | investigation | body_site | duration | severity | negation")
    tier: int = Field(ge=1, le=3, description="1: Exact, 2: Fuzzy/Orthography, 3: Constrained LLM")
    confidence: float
    negated: bool = False
    start: int = Field(default=0, description="Start character index in prepared text")
    end: int = Field(default=0, description="End character index in prepared text")
    reasoning: str | None = None
    resolution_method: str = Field(
        default="LEXICON",
        description="LEXICON | FUZZY_MATCH | LLM | OCR / VLM | ASR | HUMAN_CONFIRMED",
    )
    confirmation_required: bool = Field(
        default=False,
        description="True when field-level uncertainty requires human confirmation before record commit",
    )
    confirmation_prompt_np: str | None = Field(
        default=None,
        description="Human-in-the-loop Nepali confirmation prompt when uncertain",
    )
    icd11_code: str | None = None
    icd10_code: str | None = None
    generic: GenericRef | None = None

    @classmethod
    def from_match(cls, match: Any, lexicon: Any) -> NormalizedConcept:
        concept = match.concept
        generic = lexicon.generic_for(concept) if hasattr(lexicon, "generic_for") else None
        return cls(
            concept_id=concept.concept_id,
            surface_form=match.surface_form,
            canonical_en=concept.canonical_en,
            canonical_np=concept.canonical_np,
            concept_type=concept.concept_type,
            tier=match.tier,
            confidence=match.confidence,
            negated=match.negated,
            start=match.start_char,
            end=match.end_char,
            reasoning=match.reasoning,
            resolution_method=getattr(match, "resolution_method", "LEXICON"),
            confirmation_required=getattr(match, "confirmation_required", False),
            confirmation_prompt_np=getattr(match, "confirmation_prompt_np", None),
            icd11_code=concept.icd11_code,
            icd10_code=concept.icd10_code,
            generic=(
                GenericRef(
                    concept_id=generic.concept_id,
                    canonical_en=generic.canonical_en,
                    canonical_np=generic.canonical_np,
                )
                if generic
                else None
            ),
        )


class FieldUncertainty(BaseModel):
    """Field-level uncertainty representation separating certainty across clinical fields."""
    field: str | None = None
    value: Any
    confidence: float
    resolution_method: str = "LEXICON"
    confirmation_required: bool = False
    confirmation_prompt_np: str | None = None
    reason: str | None = None


class NormalizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    use_model: bool = Field(
        default=True,
        description="Whether Tier 3 constrained model routing is allowed on unresolved spans"
    )


class NormalizeResponse(BaseModel):
    text: str = ""
    prepared_text: str = ""
    concepts: list[NormalizedConcept] = Field(default_factory=list)
    modifiers: list[NormalizedConcept] = Field(
        default_factory=list,
        description="Body sites, durations, and negation markers"
    )
    duration_days: int | None = None
    frequency_per_day: int | None = None
    severity: str | None = None
    requires_confirmation: bool = False
    confirmation_required: bool = False
    field_uncertainty: dict[str, FieldUncertainty] = Field(default_factory=dict)
    unmatched: list[str] = Field(default_factory=list)
    tier_counts: dict[int, int] = Field(default_factory=dict)

    @classmethod
    def from_result(cls, result: Any, lexicon: Any) -> NormalizeResponse:
        assertions = result.assertions
        concepts = [NormalizedConcept.from_match(m, lexicon) for m in assertions]
        modifiers = [NormalizedConcept.from_match(m, lexicon) for m in result.matches if m not in assertions]

        # Build field-level uncertainty map
        field_unc: dict[str, FieldUncertainty] = {}
        primary_symptom = next((c for c in concepts if c.concept_type in {"symptom", "condition"}), None)
        if primary_symptom:
            field_unc["symptom"] = FieldUncertainty(
                field="symptom",
                value=primary_symptom.canonical_en.lower(),
                confidence=primary_symptom.confidence,
                resolution_method=primary_symptom.resolution_method,
                confirmation_required=primary_symptom.confirmation_required,
                confirmation_prompt_np=primary_symptom.confirmation_prompt_np,
            )
        if result.duration_days is not None:
            field_unc["duration"] = FieldUncertainty(
                field="duration",
                value=f"{result.duration_days} days",
                confidence=0.95,
                resolution_method="LEXICON",
                confirmation_required=False,
            )
        if getattr(result, "severity", None) is not None:
            sev_match = next((c for c in concepts if c.concept_type == "severity"), None)
            sev_conf = sev_match.confidence if sev_match else 0.78
            field_unc["severity"] = FieldUncertainty(
                field="severity",
                value=result.severity,
                confidence=sev_conf,
                resolution_method=sev_match.resolution_method if sev_match else "LEXICON",
                confirmation_required=sev_conf < 0.85,
            )

        req_conf = any(c.confirmation_required for c in concepts)
        return cls(
            text=result.text,
            prepared_text=result.prepared_text,
            concepts=concepts,
            modifiers=modifiers,
            duration_days=result.duration_days,
            frequency_per_day=result.frequency_per_day,
            severity=getattr(result, "severity", None),
            requires_confirmation=req_conf,
            confirmation_required=req_conf,
            field_uncertainty=field_unc,
            unmatched=result.unmatched,
            tier_counts=result.tier_counts(),
        )


class LexiconEntry(BaseModel):
    """Individual concept in the clinical lexicon."""
    concept_id: str
    canonical_en: str
    canonical_np: str
    concept_type: str
    preferred_register: str | None = None
    devanagari_aliases: list[str] = Field(default_factory=list)
    romanized_aliases: list[str] = Field(default_factory=list)
    latin_aliases: list[str] = Field(default_factory=list)
    generic_of: str | None = None
    icd11_code: str | None = None
    icd10_code: str | None = None
    negation_sensitive: bool = False
    duration_days: int | None = None
    frequency_per_day: int | None = None


class LexiconResponse(BaseModel):
    total: int
    counts_by_type: dict[str, int]
    license: str = "CC-BY-4.0"
    review_status: str = "clinician review pending"
    entries: list[LexiconEntry]


# ==============================================================================
# 2. Intake & Ingestion Pipeline Contracts (OCR, PDF, Text, & Speech)
# ==============================================================================

class CorrectionOut(BaseModel):
    """Individual OCR or phonetic correction applied to transcript."""
    original: str
    replacement: str
    start: int
    end: int
    reason: str
    confidence: float


class InlineNote(BaseModel):
    """Warning or informational hint produced during pipeline execution."""
    level: str = Field(description="info | warning | error")
    message_np: str
    message_en: str


class IntakeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    use_model: bool = True
    correct: bool = Field(
        default=True,
        description="Run lexicon-constrained OCR/spelling correction"
    )


class SpeechIntakeRequest(BaseModel):
    """Spoken Nepali clinical assessment transcript (FCHV or patient speech path)."""
    transcript: str = Field(min_length=1, max_length=20000)
    asr_confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    speaker_role: str = Field(default="fchv", description="fchv | patient | clinician")
    use_model: bool = True
    correct: bool = True


class IntakeResponse(BaseModel):
    raw_transcript: str = Field(description="Verbatim extraction from vision/document/speech")
    corrected_text: str
    extraction_method: str = Field(
        description="pymupdf | gemma4_vlm | gemma4_audio | asr_transcript | direct | unavailable"
    )
    extraction_status: str = Field(description="ok | engine_unavailable | empty | unsupported")
    input_type: str = Field(description="text | image | pdf | voice")
    document_class: str = Field(description="prescription | lab_report | bill | note | fchv_assessment")
    document_class_evidence: list[str] = Field(default_factory=list)
    corrections: list[CorrectionOut] = Field(default_factory=list)
    unverified: list[str] = Field(default_factory=list)
    asset_path: str | None = None
    pages: int | None = None
    asr_confidence: float | None = None
    confirmation_required: bool = False
    field_uncertainties: list[FieldUncertainty] = Field(default_factory=list)
    notes: list[InlineNote] = Field(default_factory=list)
    normalized: NormalizeResponse | None = None


# ==============================================================================
# 3. Patient & Record Timeline Contracts
# ==============================================================================

class Allergy(BaseModel):
    substance_en: str
    substance_np: str | None = None
    severity: str | None = None


class ConditionRef(BaseModel):
    concept_id: str
    canonical_en: str
    canonical_np: str
    icd11_code: str | None = None
    icd10_code: str | None = None


class PatientSummary(BaseModel):
    id: str
    name: str
    name_np: str | None = None
    sanjaal_id: str = Field(default="SS-NP-0001", description="SwasthyaSanjaal patient identifier")
    sanchai_id: str = Field(default="SANCHAI-0001", description="Compatible patient identifier")
    arogya_id: str | None = Field(default=None, description="Legacy identifier alias")
    age: int | None = None
    gender: str | None = None
    gender_np: str | None = None
    district: str | None = None
    blood_group: str | None = None
    entry_count: int = 0


class PatientDetail(PatientSummary):
    dob: str | None = None
    qr_token: str | None = None
    allergies: list[Allergy] = Field(default_factory=list)
    conditions: list[ConditionRef] = Field(default_factory=list)
    synthetic: bool = True


class RecordConcept(BaseModel):
    """Concept stored with a confirmed record entry."""
    concept_id: str
    canonical_en: str
    canonical_np: str
    concept_type: str
    negated: bool = False
    surface_form: str
    tier: int
    confidence: float
    start: int
    end: int
    reasoning: str | None = None
    resolution_method: str = "HUMAN_CONFIRMED"
    confirmation_required: bool = False
    icd11_code: str | None = None
    icd10_code: str | None = None
    generic: GenericRef | None = None


class RecordEntrySummary(BaseModel):
    id: str
    patient_id: str
    input_type: str
    document_class: str | None = None
    facility_name: str | None = None
    record_date: str = Field(description="Gregorian ISO-8601 (YYYY-MM-DD)")
    record_date_bs: str | None = Field(default=None, description="Bikram Sambat display string")
    extraction_method: str | None = None
    summary_np: str
    concept_count: int
    negated_count: int
    icd11_code: str | None = None
    icd10_code: str | None = None
    icd_link_status: str | None = None
    has_asset: bool = False
    tiers: list[int] = Field(default_factory=list)


class RecordEntryDetail(RecordEntrySummary):
    raw_transcript: str | None = None
    corrected_text: str | None = None
    asset_path: str | None = None
    meaning_np: str | None = None
    concepts: list[RecordConcept] = Field(default_factory=list)
    modifiers: list[RecordConcept] = Field(default_factory=list)
    duration_days: int | None = None
    frequency_per_day: int | None = None
    unmatched: list[str] = Field(default_factory=list)
    notes: list[InlineNote | dict[str, Any] | str] = Field(default_factory=list)
    dangling_concept_ids: list[str] = Field(default_factory=list)


class CommitEntryRequest(BaseModel):
    """Confirmation Layer (Approval-Before-Write gate) request model."""
    input_type: str = Field(description="text | image | pdf | voice")
    record_date: str = Field(description="Gregorian ISO-8601 (YYYY-MM-DD)")
    normalized: NormalizeResponse
    document_class: str | None = None
    facility_name: str | None = None
    record_date_bs: str | None = None
    raw_transcript: str | None = None
    corrected_text: str | None = None
    extraction_method: str | None = None
    asset_path: str | None = None
    meaning_np: str | None = None
    notes: list[InlineNote | dict[str, Any] | str] = Field(default_factory=list)


class RecordResponse(BaseModel):
    patient: PatientDetail
    entries: list[RecordEntrySummary]


# ==============================================================================
# 4. Standards, Emergency QR & Evaluation Contracts
# ==============================================================================

class QrPayload(BaseModel):
    """Emergency responder payload encoded into QR."""
    sanjaal_id: str = Field(default="SS-NP-0001", description="SwasthyaSanjaal patient identifier")
    sanchai_id: str = Field(default="SANCHAI-0001", description="Compatible patient identifier")
    arogya_id: str | None = Field(default=None, description="Legacy identifier alias")
    qr_token: str
    name: str
    name_np: str | None = None
    blood_group: str | None = None
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    synthetic: bool = True
    qr_png: str | None = None
    encodes: str | None = None


class FhirBundle(BaseModel):
    """HL7 FHIR R4 Collection Bundle strictly excluding negated concepts."""
    resourceType: str = "Bundle"
    type: str = "collection"
    entry: list[dict[str, Any]] = Field(default_factory=list)
    negated_excluded: int = 0
    synthetic: bool = True
