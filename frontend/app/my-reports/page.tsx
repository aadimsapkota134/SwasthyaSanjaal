"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  fetchMyPatient,
  fetchMyReports,
  getMyReportFileUrl,
  postIntakeFile,
  postIntakeText,
  postMyReport,
} from "@/lib/api";
import type {
  IntakeResponse,
  PatientDetail,
  RecordEntryDetail,
} from "@/lib/contracts";

export default function MyReportsPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [reports, setReports] = useState<RecordEntryDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Upload & Extraction state
  const [file, setFile] = useState<File | null>(null);
  const [textInput, setTextInput] = useState("");
  const [facilityName, setFacilityName] = useState("");
  const [documentClass, setDocumentClass] = useState("prescription");
  const [isProcessing, setIsProcessing] = useState(false);
  const [intakeResult, setIntakeResult] = useState<IntakeResponse | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }

    if (isAuthenticated) {
      if (user?.role !== "individual") {
        router.push("/");
        return;
      }

      loadData();
    }
  }, [isAuthenticated, authLoading, user]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [pat, reps] = await Promise.all([fetchMyPatient(), fetchMyReports()]);
      setPatient(pat);
      setReports(reps || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load personal records");
    } finally {
      setLoading(false);
    }
  };

  const handleExtract = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaveSuccess(null);
    setIntakeResult(null);
    setIsProcessing(true);

    try {
      let res: IntakeResponse | null = null;
      if (file) {
        res = await postIntakeFile(file, documentClass, false, true);
      } else if (textInput.trim()) {
        res = await postIntakeText(textInput.trim(), false, true);
      } else {
        setError("Please choose a file or type clinical text to extract.");
        setIsProcessing(false);
        return;
      }

      if (!res) {
        setError("Failed to extract medical content. Please verify file format.");
      } else {
        setIntakeResult(res);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSaveToRecord = async () => {
    if (!intakeResult) return;
    setIsProcessing(true);
    setError(null);

    const todayIso = new Date().toISOString().split("T")[0];
    const normalized = intakeResult.normalized ?? {
      text: intakeResult.raw_transcript,
      prepared_text: intakeResult.corrected_text || intakeResult.raw_transcript,
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
    };

    const payload = {
      input_type: intakeResult.input_type || "text",
      document_class: intakeResult.document_class || documentClass,
      facility_name: facilityName.trim() || "Health Facility",
      record_date: todayIso,
      raw_transcript: intakeResult.raw_transcript,
      corrected_text: intakeResult.corrected_text,
      extraction_method: intakeResult.extraction_method,
      asset_path: intakeResult.asset_path,
      meaning_np: normalized.prepared_text || intakeResult.corrected_text,
      normalized,
      notes: intakeResult.notes || [],
    };

    try {
      const saved = await postMyReport(payload);
      setIsProcessing(false);
      if (saved) {
        setSaveSuccess("Report successfully saved to your personal medical ledger!");
        setIntakeResult(null);
        setFile(null);
        setTextInput("");
        loadData();
      } else {
        setError("Unable to save report. Please ensure you are signed into an Individual account and try again.");
      }
    } catch (err) {
      setIsProcessing(false);
      setError(err instanceof Error ? err.message : "Unable to save report. Please check server connection.");
    }
  };

  if (authLoading || loading) {
    return (
      <div className="page">
        <div className="card panel__inner" style={{ padding: "3rem", textAlign: "center" }}>
          <p style={{ color: "var(--ink-soft)" }}>Loading your health records…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <section className="panel panel--paper">
        <div className="panel__inner">
          {/* Header */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 12,
              marginBottom: "1.5rem",
            }}
          >
            <div>
              <span className="eyebrow">Personal Portal</span>
              <h1 className="title" style={{ margin: "4px 0" }}>
                My Medical Reports & Timeline
              </h1>
              <p className="lede" style={{ margin: 0 }}>
                Upload, digitize, and generate Pre-Visit doctor summaries for your records.
              </p>
            </div>
            <Link href="/" className="button button--secondary" style={{ fontSize: "0.85rem" }}>
              ← Return Home
            </Link>
          </div>

          {error && (
            <div className="alert alert--error" style={{ marginBottom: "1.25rem" }}>
              {error}
            </div>
          )}

          {saveSuccess && (
            <div className="alert alert--success" style={{ marginBottom: "1.25rem" }}>
              ✅ {saveSuccess}
            </div>
          )}

          {/* Profile Overview Card */}
          {patient && (
            <div
              className="card"
              style={{
                marginBottom: "1.5rem",
                background: "linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%)",
                borderColor: "#a7f3d0",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "#065f46" }}>
                    {patient.name}
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "#166534", marginTop: 2 }}>
                    ID: <strong>{patient.sanjaal_id}</strong> · Blood Group: {patient.blood_group || "—"}
                  </div>
                </div>
                <div className="tag tag--committed" style={{ background: "#d1fae5", color: "#065f46" }}>
                  Active Health Account
                </div>
              </div>
            </div>
          )}

          {/* Two-Column Workspace: Left Upload/Extract, Right List Reports */}
          <div className="grid-2" style={{ alignItems: "start", gap: "1.5rem" }}>
            {/* Left: Upload and Pre-Visit Report Generator */}
            <div className="card">
              <div className="card__title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span>⚡</span> Pre-Visit Report Generator
              </div>
              <p style={{ fontSize: "0.85rem", color: "var(--ink-soft)", marginBottom: "1rem" }}>
                Upload a prescription, lab slip, or clinic note to digitize clinical terms and generate a doctor-ready summary.
              </p>

              <form onSubmit={handleExtract} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div>
                  <label className="label" style={{ fontSize: "0.85rem" }}>
                    Document Type
                  </label>
                  <select
                    className="select"
                    value={documentClass}
                    onChange={(e) => setDocumentClass(e.target.value)}
                  >
                    <option value="prescription">Prescription (Doctor Rx)</option>
                    <option value="lab_report">Lab Report (Blood, Urine, Test)</option>
                    <option value="note">Doctor Note / Discharge Slip</option>
                    <option value="bill">Pharmacy Bill</option>
                  </select>
                </div>

                <div>
                  <label className="label" style={{ fontSize: "0.85rem" }}>
                    Facility / Clinic Name (Optional)
                  </label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. Bir Hospital, Teaching Hospital, Local Health Post"
                    value={facilityName}
                    onChange={(e) => setFacilityName(e.target.value)}
                  />
                </div>

                <div>
                  <label className="label" style={{ fontSize: "0.85rem" }}>
                    Upload Document (PDF or Image)
                  </label>
                  <input
                    type="file"
                    accept="image/*,application/pdf"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    className="input"
                    style={{ padding: "0.4rem" }}
                  />
                </div>

                <div style={{ textAlign: "center", color: "var(--ink-soft)", fontSize: "0.8rem" }}>
                  — OR ENTER CLINICAL TEXT DIRECTLY —
                </div>

                <div>
                  <textarea
                    className="textarea"
                    rows={3}
                    placeholder="e.g. सिटामोल 500 एमजी दिनको २ पटक, खोकी छ, ज्वरो छैन"
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isProcessing}
                  className="button button--primary"
                  style={{ width: "100%", padding: "0.6rem" }}
                >
                  {isProcessing ? "Processing Document…" : "🔍 Extract & Generate Summary"}
                </button>
              </form>

              {/* Extraction Preview Box */}
              {intakeResult && (
                <div
                  style={{
                    marginTop: "1.5rem",
                    padding: "1rem",
                    background: "#f8fafc",
                    border: "1px solid #cbd5e1",
                    borderRadius: 12,
                  }}
                >
                  <div style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--ink)", marginBottom: 8 }}>
                    📋 Digitize & Review Preview
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--ink-soft)", marginBottom: 8 }}>
                    Extraction Method: <strong>{intakeResult.extraction_method}</strong> · Status: {intakeResult.extraction_status}
                  </div>
                  <div style={{ fontSize: "0.85rem", background: "#fff", padding: "8px 12px", borderRadius: 8, border: "1px solid #e2e8f0" }}>
                    <strong>Text:</strong> {intakeResult.corrected_text || intakeResult.raw_transcript}
                  </div>

                  {intakeResult.normalized?.concepts && intakeResult.normalized.concepts.length > 0 && (
                    <div style={{ marginTop: 10 }}>
                      <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>Identified Terms:</span>
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
                        {intakeResult.normalized.concepts.map((c, i) => (
                          <span key={i} className="tag tag--committed" style={{ fontSize: "0.75rem" }}>
                            {c.canonical_np} ({c.canonical_en})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <button
                    onClick={handleSaveToRecord}
                    disabled={isProcessing}
                    className="button button--primary"
                    style={{ width: "100%", marginTop: "1rem", background: "#059669" }}
                  >
                    💾 Save to My Health Record
                  </button>
                </div>
              )}
            </div>

            {/* Right: Existing Documents & Timeline */}
            <div className="card">
              <div className="card__title">My Saved Documents ({reports.length})</div>
              {reports.length === 0 ? (
                <div className="empty-state" style={{ padding: "2rem 1rem" }}>
                  <div className="empty-state__icon">📁</div>
                  <div className="empty-state__title">No medical reports yet</div>
                  <p className="empty-state__desc">
                    Upload your first prescription or lab test using the generator on the left.
                  </p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem" }}>
                  {reports.map((r) => {
                    const mainText = r.corrected_text || r.raw_transcript || r.summary_np;
                    const summaryPoints = r.meaning_np || r.summary_np;
                    const hasAttachment = Boolean(r.asset_path);

                    return (
                      <div
                        key={r.id}
                        style={{
                          padding: "1.25rem",
                          borderRadius: 14,
                          border: "1px solid #e2e8f0",
                          background: "#ffffff",
                          boxShadow: "0 2px 8px rgba(0, 0, 0, 0.04)",
                          display: "flex",
                          flexDirection: "column",
                          gap: "0.85rem",
                        }}
                      >
                        {/* Header with facility, date, and document type */}
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
                          <div>
                            <div style={{ fontWeight: 800, fontSize: "1rem", color: "var(--ink)" }}>
                              🏥 {r.facility_name || "Health Post / Clinic"}
                            </div>
                            <div style={{ fontSize: "0.8rem", color: "var(--ink-soft)", marginTop: 2 }}>
                              📅 {r.record_date} {r.record_date_bs && `(${r.record_date_bs})`} · Type: <span style={{ textTransform: "capitalize", fontWeight: 600 }}>{r.document_class || "Document"}</span>
                            </div>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span className="tag tag--neutral" style={{ textTransform: "uppercase", fontSize: "0.65rem", letterSpacing: "0.5px" }}>
                              {r.extraction_method || "direct"}
                            </span>
                            {hasAttachment && (
                              <span className="tag tag--committed" style={{ fontSize: "0.65rem" }}>
                                📎 Attached
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Div 1: Main Extracted Clinical Text */}
                        <div
                          style={{
                            background: "#f8fafc",
                            border: "1px solid #cbd5e1",
                            borderRadius: 10,
                            padding: "0.75rem 1rem",
                          }}
                        >
                          <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", color: "#475569", marginBottom: 4, letterSpacing: "0.5px" }}>
                            📄 Main Extracted Content (मुख्य पाठ)
                          </div>
                          <div style={{ fontSize: "0.9rem", color: "#0f172a", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
                            {mainText}
                          </div>
                        </div>

                        {/* Div 2: Small Text Summarizing Important Points */}
                        <div
                          style={{
                            background: "linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%)",
                            border: "1px solid #a7f3d0",
                            borderRadius: 10,
                            padding: "0.75rem 1rem",
                          }}
                        >
                          <div style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase", color: "#065f46", marginBottom: 4, letterSpacing: "0.5px" }}>
                            💡 Summary & Key Clinical Points (महत्वपूर्ण बुँदाहरू)
                          </div>
                          <div style={{ fontSize: "0.85rem", color: "#166534", lineHeight: 1.45 }}>
                            {summaryPoints}
                          </div>

                          {/* Concepts badge row */}
                          {r.concepts && r.concepts.length > 0 && (
                            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                              {r.concepts.map((c, idx) => (
                                <span
                                  key={idx}
                                  style={{
                                    fontSize: "0.72rem",
                                    fontWeight: 600,
                                    background: "#ffffff",
                                    color: "#065f46",
                                    padding: "2px 8px",
                                    borderRadius: 12,
                                    border: "1px solid #bbf7d0",
                                  }}
                                >
                                  💊 {c.canonical_np} ({c.canonical_en})
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Div 3: Action Bar with Open Report File Option */}
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            paddingTop: "0.5rem",
                            borderTop: "1px dashed #e2e8f0",
                          }}
                        >
                          <div style={{ fontSize: "0.75rem", color: "var(--ink-soft)" }}>
                            ID: <code style={{ fontSize: "0.75rem" }}>{r.id}</code>
                          </div>
                          <div>
                            {hasAttachment ? (
                              <a
                                href={getMyReportFileUrl(r.id)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="button button--secondary"
                                style={{
                                  fontSize: "0.8rem",
                                  padding: "0.35rem 0.85rem",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 6,
                                  textDecoration: "none",
                                }}
                              >
                                <span>👁️</span> Open Original Document
                              </a>
                            ) : (
                              <span style={{ fontSize: "0.75rem", color: "#94a3b8", fontStyle: "italic" }}>
                                Direct clinical text entry (no attachment)
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
