export type GenericRef = {
  concept_id: string;
  canonical_en: string;
  canonical_np: string;
};

export type FieldUncertainty = {
  field: string | null;
  value: unknown;
  confidence: number;
  resolution_method: string;
  confirmation_required: boolean;
  confirmation_prompt_np: string | null;
  reason: string | null;
};

export type NormalizedConcept = {
  concept_id: string;
  surface_form: string;
  canonical_en: string;
  canonical_np: string;
  concept_type: string;
  tier: 1 | 2 | 3;
  confidence: number;
  negated: boolean;
  start: number;
  end: number;
  reasoning: string | null;
  resolution_method: string;
  confirmation_required: boolean;
  confirmation_prompt_np: string | null;
  icd11_code: string | null;
  icd10_code: string | null;
  generic: GenericRef | null;
};

export type NormalizeResponse = {
  text: string;
  prepared_text: string;
  concepts: NormalizedConcept[];
  modifiers: NormalizedConcept[];
  duration_days: number | null;
  frequency_per_day: number | null;
  severity: string | null;
  requires_confirmation: boolean;
  confirmation_required: boolean;
  field_uncertainty: Record<string, FieldUncertainty>;
  unmatched: string[];
  tier_counts: Record<string, number>;
};

export type CorrectionOut = {
  original: string;
  replacement: string;
  start: number;
  end: number;
  reason: string;
  confidence: number;
};

export type InlineNote = {
  level: "info" | "warning" | "error";
  message_np: string;
  message_en: string;
};

export type IntakeResponse = {
  raw_transcript: string;
  corrected_text: string;
  extraction_method: string;
  extraction_status: string;
  input_type: string;
  document_class: string;
  document_class_evidence: string[];
  corrections: CorrectionOut[];
  unverified: string[];
  asset_path: string | null;
  pages: number | null;
  asr_confidence: number | null;
  confirmation_required: boolean;
  field_uncertainties: FieldUncertainty[];
  notes: InlineNote[];
  normalized: NormalizeResponse | null;
};

export type Allergy = {
  substance_en: string;
  substance_np: string | null;
  severity: string | null;
};

export type ConditionRef = {
  concept_id: string;
  canonical_en: string;
  canonical_np: string;
  icd11_code: string | null;
  icd10_code: string | null;
};

export type PatientSummary = {
  id: string;
  name: string;
  name_np: string | null;
  sanjaal_id: string;
  sanchai_id: string;
  arogya_id: string | null;
  age: number | null;
  gender: string | null;
  gender_np: string | null;
  district: string | null;
  blood_group: string | null;
  entry_count: number;
};

export type PatientDetail = PatientSummary & {
  dob: string | null;
  qr_token: string | null;
  allergies: Allergy[];
  conditions: ConditionRef[];
  synthetic: boolean;
};

export type RecordConcept = {
  concept_id: string;
  canonical_en: string;
  canonical_np: string;
  concept_type: string;
  negated: boolean;
  surface_form: string;
  tier: number;
  confidence: number;
  start: number;
  end: number;
  reasoning: string | null;
  resolution_method: string;
  confirmation_required: boolean;
  icd11_code: string | null;
  icd10_code: string | null;
  generic: GenericRef | null;
};

export type RecordEntrySummary = {
  id: string;
  patient_id: string;
  input_type: string;
  document_class: string | null;
  facility_name: string | null;
  record_date: string;
  record_date_bs: string | null;
  extraction_method: string | null;
  summary_np: string;
  concept_count: number;
  negated_count: number;
  icd11_code: string | null;
  icd10_code: string | null;
  icd_link_status: string | null;
  has_asset: boolean;
  tiers: number[];
};

export type RecordEntryDetail = RecordEntrySummary & {
  raw_transcript: string | null;
  corrected_text: string | null;
  asset_path: string | null;
  meaning_np: string | null;
  concepts: RecordConcept[];
  modifiers: RecordConcept[];
  duration_days: number | null;
  frequency_per_day: number | null;
  unmatched: string[];
  notes: Array<InlineNote | Record<string, unknown> | string>;
  dangling_concept_ids: string[];
};

export type QrPayload = {
  sanjaal_id: string;
  sanchai_id: string;
  arogya_id: string | null;
  qr_token: string;
  name: string;
  name_np: string | null;
  blood_group: string | null;
  allergies: string[];
  conditions: string[];
  synthetic: boolean;
  qr_png: string | null;
  encodes: string | null;
};

export type FhirBundle = {
  resourceType: string;
  type: string;
  entry: Array<Record<string, unknown>>;
  negated_excluded: number;
  synthetic: boolean;
};

export type CategoryRow = {
  category: string;
  total: number;
  exact: number;
  accuracy: number;
};

export type ItemRow = {
  item_id: number;
  category: string;
  derivation: string;
  input: string;
  gold_present: string[];
  gold_negated: string[];
  predicted_present: string[];
  predicted_negated: string[];
  tier_fired: number | null;
  correct: boolean;
  missed: string[];
  spurious: string[];
};

export type EvalRunResponse = {
  run_id: string;
  created_at: string;
  use_model: boolean;
  persisted: boolean;
  total: number;
  exact: number;
  accuracy: number;
  negation_total: number;
  negation_correct: number;
  duration_total: number;
  duration_correct: number;
  precision: number;
  recall: number;
  f1: number;
  tier_counts: Record<string, number>;
  tier_precision: Record<string, number | null>;
  model_share: number;
  by_category: CategoryRow[];
  brand_items: number;
  brand_resolved: number;
  derivation_counts: Record<string, number>;
  caveats: string[];
  items: ItemRow[];
};

// ---- Authentication types ----

export type LoginRequest = {
  email: string;
  password: string;
};

export type UserResponse = {
  user_id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type CreateUserRequest = {
  email: string;
  password: string;
  full_name?: string | null;
  role: "administrator" | "clinician";
};

export type UpdateUserRequest = {
  is_active?: boolean | null;
  role?: "administrator" | "clinician" | null;
  full_name?: string | null;
};
