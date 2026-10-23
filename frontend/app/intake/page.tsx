"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchPatients,
  postCommitEntry,
  postIntakeFile,
  postIntakeText,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type {
  FieldUncertainty,
  IntakeResponse,
  NormalizedConcept,
  PatientSummary,
} from "@/lib/contracts";

type Step = "input" | "results" | "review" | "success" | "error";

export default function IntakePage() {
  const { isAuthenticated, isLoading } = useAuth();
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [step, setStep] = useState<Step>("input");
  const [inputText, setInputText] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [useModel, setUseModel] = useState(false);
  const [applyCorrection, setApplyCorrection] = useState(true);
  const [documentClass, setDocumentClass] = useState<"prescription" | "lab_report" | "bill" | "note" | null>(null);
  const [intakeResult, setIntakeResult] = useState<IntakeResponse | null>(null);
  const [commitRecordDate, setCommitRecordDate] = useState("");
  const [commitFacility, setCommitFacility] = useState("");
  const [commitMeaningNp, setCommitMeaningNp] = useState("");
  const [processing, setProcessing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [commitSuccess, setCommitSuccess] = useState<{ id: string; patientName: string } | null>(null);
  const [commitError, setCommitError] = useState<string | null>(null);

  // Load patients on mount - hooks must be called before any early returns
  useEffect(() => {
    if (!isAuthenticated || isLoading) return;
    fetchPatients().then((p) => {
      if (p) setPatients(p);
      if (p && p.length > 0 && !selectedPatientId) setSelectedPatientId(p[0].id);
    });
  }, [isAuthenticated, isLoading, selectedPatientId]);

  // Require authentication
  if (!isAuthenticated) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="page">
        <div className="card panel__inner" style={{ padding: "3rem 1rem", textAlign: "center" }}>
          <p style={{ color: "var(--ink-soft)" }}>Loading…</p>
        </div>
      </div>
    );
  }

  const documentClasses: { value: "prescription" | "lab_report" | "bill" | "note"; label: string }[] = [
    { value: "prescription", label: "Prescription slip" },
    { value: "lab_report", label: "Laboratory report" },
    { value: "bill", label: "Bill / invoice" },
    { value: "note", label: "Clinical note" },
  ];

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  };
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
  };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) setSelectedFile(files[0]);
  };

  const handleSubmitInput = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) {
      setError("Please enter some clinical text.");
      return;
    }
    setProcessing(true);
    setError(null);
    try {
      const result = await postIntakeText(inputText, useModel, applyCorrection);
      if (!result) {
        setError("Backend did not return a valid response.");
        setStep("error");
        return;
      }
      setIntakeResult(result);
      setStep("results");
    } catch {
      setError("Failed to process text intake.");
      setStep("error");
    } finally {
      setProcessing(false);
    }
  };

  const handleSubmitFile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError("Please select a file to upload.");
      return;
    }
    setProcessing(true);
    setError(null);
    try {
      const result = await postIntakeFile(selectedFile, documentClass ?? null, useModel, applyCorrection);
      if (!result) {
        setError("Backend did not return a valid response.");
        setStep("error");
        return;
      }
      setIntakeResult(result);
      setStep("results");
    } catch {
      setError("Failed to process file upload.");
      setStep("error");
    } finally {
      setProcessing(false);
    }
  };

  const handleReview = () => {
    if (!intakeResult) return;
    const today = new Date().toISOString().slice(0, 10);
    setCommitRecordDate(today);
    setCommitFacility("");
    setCommitMeaningNp("");
    setCommitError(null);
    setStep("review");
  };

  const handleCommit = async () => {
    if (!intakeResult || !selectedPatientId) {
      setCommitError("Patient and intake result are required.");
      return;
    }
    setProcessing(true);
    setCommitError(null);
    try {
      const normalized = intakeResult.normalized;
      const payload: Record<string, unknown> = {
        input_type: intakeResult.input_type,
        record_date: commitRecordDate || new Date().toISOString().slice(0, 10),
        normalized: normalized ?? {
          text: intakeResult.raw_transcript,
          prepared_text: intakeResult.corrected_text,
          concepts: [],
          modifiers: [],
          duration_days: null,
          frequency_per_day: null,
          severity: null,
          requires_confirmation: false,
          confirmation_required: false,
          field_uncertainty: {},
          unmatched: [],
          tier_counts: {},
        },
        document_class: intakeResult.document_class,
        facility_name: commitFacility || null,
        record_date_bs: null,
        raw_transcript: intakeResult.raw_transcript,
        corrected_text: intakeResult.corrected_text,
        extraction_method: intakeResult.extraction_method,
        meaning_np: commitMeaningNp || null,
        notes: intakeResult.notes ?? [],
      };
      const created = await postCommitEntry(selectedPatientId, payload);
      if (!created) {
        setCommitError("Commit was rejected by the backend. Please check the review form and try again.");
        return;
      }
      setCommitSuccess({ id: created.id, patientName: selectedPatientId });
      setStep("success");
    } catch {
      setCommitError("An unexpected error occurred during commit.");
    } finally {
      setProcessing(false);
    }
  };

  const handleReset = () => {
    setStep("input");
    setInputText("");
    setSelectedFile(null);
    setIntakeResult(null);
    setError(null);
    setCommitError(null);
    setCommitSuccess(null);
  };

  const patientOption = patients?.find((p) => p.id === selectedPatientId);

  return (
    <div className="page">
      <Link href="/" className="button button--ghost" style={{ marginBottom: "1rem", display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
        ← Back to dashboard
      </Link>

      {/* Step: Input */}
      {step === "input" && (
        <section className="panel panel--paper">
          <div className="panel__inner">
            <span className="eyebrow">Document intake</span>
            <h1 className="title">Enter or upload clinical notes</h1>
            <p className="lede">
              Submit clinical text, a prescription photo, or a lab-report PDF. The backend
              extracts text, normalizes it against the Nepali clinical lexicon, and surfaces
              negation and uncertainty for your review before anything is saved.
            </p>

            {error && <div className="alert alert--error">{error}</div>}

            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1.5rem", alignItems: "start" }}>
              {/* Patient selector */}
              <div className="card">
                <div className="field">
                  <label className="field__label">Commit to patient</label>
                  <select
                    className="field__select"
                    value={selectedPatientId}
                    onChange={(e) => setSelectedPatientId(e.target.value)}
                  >
                    {patients?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name_np ? `${p.name} (${p.name_np})` : p.name} — {p.sanjaal_id}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Text input */}
              <div className="card">
                <div className="field">
                  <label className="field__label">Clinical text</label>
                  <textarea
                    className="field__textarea"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    placeholder="e.g. ज्वरो छैन, खोकी छ, सिटामोल ५०० एमजी"
                  />
                  <p className="field__hint">Supports Devanagari, Romanized Nepali, English, and code-mixed text.</p>
                </div>
                <div className="actions" style={{ marginTop: "0.75rem" }}>
                  <button
                    onClick={handleSubmitInput}
                    className="button button--primary"
                    disabled={processing || !inputText.trim()}
                  >
                    {processing ? "Processing…" : "⚡ Run intake pipeline"}
                  </button>
                </div>
              </div>

              {/* File upload */}
              <div className="card">
                <div className="field">
                  <label className="field__label">Upload file (PDF or image)</label>
                  <div
                    className={`drop-zone ${dragActive ? "drop-zone--drag" : ""}`}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    role="button"
                    tabIndex={0}
                  >
                    <p style={{ margin: 0, fontWeight: 600, color: "var(--ink)" }}>
                      {selectedFile ? selectedFile.name : "Drag & drop a PDF or image here"}
                    </p>
                    <p className="drop-zone__hint">Supports PDF, PNG, JPG, WebP, HEIC. Max 25 MB.</p>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg,.webp,.heic"
                      style={{ display: "none" }}
                      onChange={(e) => {
                        if (e.target.files?.length) setSelectedFile(e.target.files[0]);
                      }}
                    />
                    <button
                      type="button"
                      onClick={(e) => {
                        const input = e.currentTarget.querySelector("input[type=file]") as HTMLInputElement | null;
                        input?.click();
                      }}
                      className="button button--secondary"
                      style={{ marginTop: "0.75rem", fontSize: "0.85rem", padding: "0.45rem 0.9rem" }}
                    >
                      Browse files
                    </button>
                  </div>
                </div>
                <div className="field" style={{ marginTop: "0.75rem" }}>
                  <label className="field__label">Document class (optional hint)</label>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {documentClasses.map((dc) => (
                      <button
                        key={dc.value}
                        onClick={() => setDocumentClass(dc.value)}
                        className="button button--ghost"
                        style={{
                          flex: 1,
                          minWidth: 120,
                          border: `1px solid ${documentClass === dc.value ? "var(--brand)" : "var(--line)"}`,
                          color: documentClass === dc.value ? "var(--brand)" : "var(--ink-soft)",
                          background: documentClass === dc.value ? "#ecfdf5" : "transparent",
                        }}
                      >
                        {dc.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="actions" style={{ marginTop: "0.75rem" }}>
                  <button
                    onClick={handleSubmitFile}
                    className="button button--primary"
                    disabled={processing || !selectedFile}
                  >
                    {processing ? "Processing…" : "📤 Process upload"}
                  </button>
                </div>
              </div>

              {/* Options */}
              <div className="card">
                <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "0.75rem" }}>
                  <input
                    id="use-model"
                    type="checkbox"
                    checked={useModel}
                    onChange={(e) => setUseModel(e.target.checked)}
                  />
                  <label htmlFor="use-model" style={{ fontSize: "0.9rem", color: "var(--ink)", cursor: "pointer", margin: 0 }}>
                    Enable Tier 3 (constrained model) candidate selection
                  </label>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                  <input
                    id="apply-correction"
                    type="checkbox"
                    checked={applyCorrection}
                    onChange={(e) => setApplyCorrection(e.target.checked)}
                  />
                  <label htmlFor="apply-correction" style={{ fontSize: "0.9rem", color: "var(--ink)", cursor: "pointer", margin: 0 }}>
                    Run lexicon-constrained correction
                  </label>
                </div>
                <p style={{ fontSize: "0.8rem", color: "var(--ink-soft)", margin: "0.5rem 0 0 0" }}>
                  Tier 3 and vision OCR require a reachable Ollama/Gemma backend. Deterministic
                  lexicon matching works offline.
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Step: Results */}
      {step === "results" && intakeResult && (
        <section className="panel panel--paper">
          <div className="panel__inner">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
              <div>
                <span className="eyebrow">Intake results — review before saving</span>
                <h1 className="title">Extracted & normalized findings</h1>
              </div>
              <button onClick={handleReset} className="button button--secondary" style={{ fontSize: "0.85rem" }}>
                Start over
              </button>
            </div>

            {intakeResult.extraction_status !== "ok" && (
              <div className="alert alert--warning">
                Extraction status: <strong>{intakeResult.extraction_status}</strong>.{" "}
                {intakeResult.notes.find((n) => n.level === "error")?.message_en || ""}
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1.5rem" }}>
              {/* Raw vs corrected */}
              <div className="card">
                <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <span style={{ fontSize: "0.8rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--ink-soft)" }}>Raw transcript</span>
                  <span className={`tag ${intakeResult.extraction_method === "pymupdf" ? "tag--committed" : "tag--review"}`}>
                    {intakeResult.extraction_method.replace(/_/g, " ").toUpperCase()}
                  </span>
                </div>
                <div className="intake-text">{intakeResult.raw_transcript}</div>
                <p style={{ fontSize: "0.8rem", color: "var(--ink-soft)", marginTop: "0.5rem" }}>
                  Corrected: <strong>{intakeResult.corrected_text}</strong>
                </p>
              </div>

              {/* Meta */}
              <div className="card">
                <div className="metrics" style={{ gap: "0.75rem" }}>
                  <article className="metric">
                    <span className="metric__label">Document class</span>
                    <div className="metric__value">{intakeResult.document_class.replace(/_/g, " ")}</div>
                  </article>
                  <article className="metric">
                    <span className="metric__label">Status</span>
                    <div className="metric__value">{intakeResult.extraction_status}</div>
                  </article>
                  <article className="metric">
                    <span className="metric__label">Concepts</span>
                    <div className="metric__value">{intakeResult.normalized?.concepts.length ?? 0}</div>
                  </article>
                  <article className="metric">
                    <span className="metric__label">Negated</span>
                    <div className="metric__value" style={{ color: "var(--danger)" }}>
                      {intakeResult.normalized?.concepts.filter((c: NormalizedConcept) => c.negated).length}
                    </div>
                  </article>
                </div>
                {intakeResult.confirmation_required && (
                  <div className="alert alert--warning" style={{ marginTop: "1rem" }}>
                    ⚠️ Human confirmation required before this can be committed to a patient record.
                  </div>
                )}
                {intakeResult.unverified.length > 0 && (
                  <div className="alert alert--info" style={{ marginTop: "0.75rem" }}>
                    <strong>Unverified tokens:</strong> {intakeResult.unverified.join(", ")}
                  </div>
                )}
              </div>

              {/* Corrections */}
              {intakeResult.corrections.length > 0 && (
                <div className="card">
                  <div className="card__title">Lexicon corrections</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {intakeResult.corrections.map((c, i) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", padding: "0.4rem", background: "#f8fafc", borderRadius: "6px" }}>
                        <span>&quot;{c.original}&quot; &rarr; &quot;{c.replacement}&quot;</span>
                        <span className="tag tag--neutral" style={{ fontSize: "0.7rem" }}>{c.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Concepts */}
              <div className="card">
                <div className="card__title">Normalized clinical concepts</div>
                {intakeResult.normalized?.concepts?.length === 0 ? (
                  <p style={{ color: "var(--ink-soft)", fontSize: "0.9rem", margin: 0 }}>No clinical concepts recognized.</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {intakeResult.normalized?.concepts?.map((c: NormalizedConcept, i: number) => (
                      <div key={`${c.concept_id}-${i}`} className="concept-chip">
                        <div>
                          <div className="concept-chip__name">{c.canonical_en}</div>
                          <div className="concept-chip__np">{c.canonical_np}</div>
                        </div>
                        <div className="concept-chip__meta">
                          <span className={`tag tag--tier${c.tier}`} style={{ fontSize: "0.7rem" }}>Tier {c.tier}</span>
                          {c.negated && <span className="concept-chip__negated">Negated</span>}
                          {c.generic && (
                            <span className="tag" style={{ background: "#e0e7ff", color: "#1e3a8a", fontSize: "0.7rem" }}>
                              Generic: {c.generic.canonical_en}
                            </span>
                          )}
                          <span style={{ fontSize: "0.7rem", color: "var(--neutral)" }}>
                            Confidence: {(c.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Modifiers */}
              {intakeResult.normalized?.modifiers && intakeResult.normalized.modifiers.length > 0 && (
                <div className="card">
                  <div className="card__title">Modifiers (duration, frequency, severity)</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                    {intakeResult.normalized.modifiers.map((m: NormalizedConcept, i: number) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", padding: "0.4rem", background: "#f8fafc", borderRadius: "6px" }}>
                        <span>{m.canonical_np} ({m.canonical_en})</span>
                        <span className="tag tag--neutral" style={{ fontSize: "0.7rem" }}>{m.concept_type}</span>
                      </div>
                    ))}
                    {intakeResult.normalized.duration_days && (
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", padding: "0.4rem", background: "#f8fafc", borderRadius: "6px" }}>
                        <span>Duration: {intakeResult.normalized.duration_days} days</span>
                      </div>
                    )}
                    {intakeResult.normalized.frequency_per_day && (
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", padding: "0.4rem", background: "#f8fafc", borderRadius: "6px" }}>
                        <span>Frequency: {intakeResult.normalized.frequency_per_day}x/day</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Field uncertainties */}
              {intakeResult.field_uncertainties && intakeResult.field_uncertainties.length > 0 && (
                <div className="card">
                  <div className="card__title">Field-level uncertainty</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                    {intakeResult.field_uncertainties.map((u: FieldUncertainty, i: number) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", padding: "0.4rem", background: u.confirmation_required ? "#fefce8" : "#f8fafc", borderRadius: "6px", border: u.confirmation_required ? "1px solid #fde047" : "none" }}>
                        <div>
                          <div style={{ fontWeight: 600 }}>{u.field}</div>
                          <div style={{ fontSize: "0.8rem", color: "var(--ink-soft)" }}>{String(u.value)}</div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <div style={{ fontSize: "0.75rem", fontWeight: 700, color: u.confirmation_required ? "var(--warning)" : "var(--ok)" }}>
                            {(u.confidence * 100).toFixed(0)}%
                          </div>
                          <div style={{ fontSize: "0.7rem", color: "var(--ink-soft)" }}>{u.reason}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="review-actions">
              <button onClick={handleReset} className="button button--secondary">
                Start over
              </button>
              <button
                onClick={handleReview}
                className="button button--primary"
                disabled={intakeResult.extraction_status !== "ok"}
              >
                ✓ Review & commit to record
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Step: Review */}
      {step === "review" && intakeResult && (
        <section className="panel panel--paper">
          <div className="panel__inner">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
              <div>
                <span className="eyebrow">Approval-before-write gate</span>
                <h1 className="title">Review before saving</h1>
              </div>
              <button onClick={() => setStep("results")} className="button button--secondary" style={{ fontSize: "0.85rem" }}>
                ← Back to results
              </button>
            </div>

            <div className="review-header">
              <div>
                <div className="field__label">Patient</div>
                <div style={{ fontWeight: 700, fontSize: "1rem" }}>
                  {patientOption?.name_np ? `${patientOption.name} (${patientOption.name_np})` : patientOption?.name}
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--ink-soft)" }}>
                  {patientOption?.sanjaal_id} · {patientOption?.blood_group || "Unknown blood group"}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="field__label">Record date</div>
                <input
                  type="date"
                  className="field__input"
                  value={commitRecordDate}
                  onChange={(e) => setCommitRecordDate(e.target.value)}
                  style={{ width: "160px", fontSize: "0.9rem" }}
                />
              </div>
            </div>

            <div className="card" style={{ marginTop: "1rem" }}>
              <div className="field__label">Facility / clinic name (optional)</div>
              <input
                className="field__input"
                value={commitFacility}
                onChange={(e) => setCommitFacility(e.target.value)}
                placeholder="e.g. Dhulikhel Hospital"
              />
            </div>

            <div className="card" style={{ marginTop: "1rem" }}>
              <div className="field__label">Meaning in Nepali (optional, for patient explanation)</div>
              <textarea
                className="field__textarea"
                value={commitMeaningNp}
                onChange={(e) => setCommitMeaningNp(e.target.value)}
                placeholder="e.g. तपाईंलाई टाइफाइड ज्वरोको लागि औषधि दिइएको छ।"
                rows={3}
              />
            </div>

            <div className="card" style={{ marginTop: "1rem" }}>
              <div className="card__title">Proposed entry summary</div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem", paddingBottom: "0.5rem", borderBottom: "1px solid var(--line)" }}>
                  <span>Input type</span>
                  <span>{intakeResult.input_type}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem", paddingBottom: "0.5rem", borderBottom: "1px solid var(--line)" }}>
                  <span>Document class</span>
                  <span>{intakeResult.document_class}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem", paddingBottom: "0.5rem", borderBottom: "1px solid var(--line)" }}>
                  <span>Extraction method</span>
                  <span>{intakeResult.extraction_method}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem" }}>
                  <span>Concepts to record</span>
                  <span>{intakeResult.normalized?.concepts.length ?? 0}</span>
                </div>
              </div>
              {intakeResult.normalized?.concepts && intakeResult.normalized.concepts.length > 0 && (
                <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                  {intakeResult.normalized.concepts.map((c: NormalizedConcept, i: number) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", padding: "0.35rem 0" }}>
                      <span dangerouslySetInnerHTML={{ __html: `${c.canonical_en} (${c.canonical_np})${c.negated ? " — <span style=&#39;color: var(--danger)&#39;><strong>NEGATED</strong></span>" : ""}` }} />
                      <span className={`tag tag--tier${c.tier}`} style={{ fontSize: "0.7rem" }}>Tier {c.tier}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {commitError && <div className="alert alert--error" style={{ marginTop: "1rem" }}>{commitError}</div>}

            <div className="review-actions" style={{ marginTop: "1.5rem" }}>
              <button onClick={() => setStep("results")} className="button button--secondary">
                Back to results
              </button>
              <button
                onClick={handleCommit}
                className="button button--primary"
                disabled={processing}
              >
                {processing ? "Committing…" : "✓ Approve & commit to patient record"}
              </button>
              <p style={{ fontSize: "0.8rem", color: "var(--ink-soft)", marginTop: "0.75rem" }}>
                Nothing is written to the patient record until you explicitly approve above.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Step: Success */}
      {step === "success" && commitSuccess && (
        <section className="panel panel--paper">
          <div className="panel__inner" style={{ textAlign: "center", padding: "3rem 1rem" }}>
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }} aria-hidden="true">✓</div>
            <h1 className="title" style={{ marginBottom: "0.5rem" }}>Record committed</h1>
            <p style={{ color: "var(--ink-soft)", marginBottom: "1.5rem" }}>
              The approved entry has been written to {commitSuccess.patientName}&#39;s longitudinal record.
            </p>
            <div className="actions" style={{ justifyContent: "center" }}>
              <Link
                href={`/patients/${commitSuccess.id}`}
                className="button button--primary"
              >
                View patient record
              </Link>
              <button
                onClick={handleReset}
                className="button button--secondary"
              >
                Record another
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Step: Error */}
      {step === "error" && (
        <section className="panel panel--paper">
          <div className="panel__inner" style={{ textAlign: "center", padding: "3rem 1rem" }}>
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }} aria-hidden="true">⚠️</div>
            <h1 className="title" style={{ marginBottom: "0.5rem" }}>Unable to process</h1>
            <p style={{ color: "var(--ink-soft)", marginBottom: "1.5rem" }}>{error}</p>
            <div className="actions" style={{ justifyContent: "center" }}>
              <button onClick={handleReset} className="button button--primary">
                Try again
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
