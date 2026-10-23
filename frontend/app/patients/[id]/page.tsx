"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  downloadPatientPdf,
  fetchPatientFhir,
  fetchPatientQr,
  fetchPatientRecord,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { PatientDetail, QrPayload, RecordEntrySummary } from "@/lib/contracts";

export default function PatientPage({
  params,
}: {
  params: { id: string } | Promise<{ id: string }>;
}) {
  const resolvedParams =
    typeof (params as any)?.then === "function"
      ? use(params as Promise<{ id: string }>)
      : (params as { id: string });
  const id = resolvedParams.id;

  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [entries, setEntries] = useState<RecordEntrySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [qrPayload, setQrPayload] = useState<QrPayload | null>(null);

  // Load patient data on mount
  useEffect(() => {
    if (authLoading || !isAuthenticated || !id) return;
    let cancelled = false;

    setLoading(true);
    Promise.all([
      fetchPatientRecord(id).then((r) => {
        if (!cancelled) {
          setPatient(r?.patient ?? null);
          setEntries(r?.entries ?? null);
        }
      }).catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load patient record");
      }),
      fetchPatientQr(id).then((q) => {
        if (!cancelled) setQrPayload(q);
      }).catch(() => {
        // QR is optional
      }),
    ]).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [id, isAuthenticated, authLoading]);

  if (authLoading || loading) {
    return (
      <div className="page">
        <div className="card panel__inner" style={{ padding: "3rem 1rem", textAlign: "center" }}>
          <p style={{ color: "var(--ink-soft)" }}>Loading patient record…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="page">
        <div className="card panel__inner" style={{ padding: "3rem 1rem", textAlign: "center" }}>
          <h2 style={{ marginBottom: "0.5rem" }}>Sign in required</h2>
          <p style={{ color: "var(--ink-soft)", marginBottom: "1.5rem" }}>
            Please sign in to view this patient&#39;s clinical record.
          </p>
          <Link href="/login" className="button button--primary">
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  if (error || !patient) {
    return (
      <div className="page">
        <div className="card panel__inner" style={{ padding: "3rem 1rem", textAlign: "center" }}>
          <h2 style={{ marginBottom: "0.5rem" }}>Patient record unavailable</h2>
          <p style={{ color: "var(--ink-soft)", marginBottom: "1.5rem" }}>
            {error || "The requested patient record could not be found or you do not have permission to view it."}
          </p>
          <Link href="/" className="button button--secondary">
            ← Return to dashboard
          </Link>
        </div>
      </div>
    );
  }

  const allergies = patient.allergies ?? [];
  const activeConditions = patient.conditions ?? [];

  return (
    <div className="page">
      <section className="panel panel--paper">
        <div className="panel__inner">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "1rem", marginBottom: "1rem" }}>
            <div>
              <Link href="/" className="button button--ghost" style={{ padding: "0.4rem 0.8rem", fontSize: "0.85rem" }}>
                ← Back to dashboard
              </Link>
              <h1 className="title" style={{ marginTop: "0.5rem" }}>
                {patient.name_np ? `${patient.name} (${patient.name_np})` : patient.name}
              </h1>
              <p style={{ color: "var(--ink-soft)", fontSize: "0.9rem", margin: "0.25rem 0 0 0" }}>
                {patient.sanjaal_id} · {patient.sanchai_id} · Synthetic demo record
              </p>
            </div>
            <div className="actions">
              <Link href={`/intake?patient=${id}`} className="button button--primary">
                📥 Add document intake
              </Link>
              <button className="button button--secondary" disabled>
                📄 PDF summary
              </button>
              <a
                href={patient.qr_token ? `/emergency/${patient.qr_token}` : "#"}
                className="button button--secondary"
                style={patient.qr_token ? undefined : { opacity: 0.5, pointerEvents: "none" }}
              >
                🚨 Emergency QR
              </a>
            </div>
          </div>

          {/* Demographics */}
          <div className="metrics" style={{ marginTop: "1rem" }}>
            <article className="metric">
              <span className="metric__label">SwasthyaSanjaal ID</span>
              <div className="metric__value">{patient.sanjaal_id}</div>
            </article>
            <article className="metric">
              <span className="metric__label">Compatible ID</span>
              <div className="metric__value">{patient.sanchai_id}</div>
            </article>
            <article className="metric">
              <span className="metric__label">Blood group</span>
              <div className="metric__value">{patient.blood_group || "Unknown"}</div>
            </article>
            <article className="metric">
              <span className="metric__label">District</span>
              <div className="metric__value">{patient.district || "—"}</div>
            </article>
            <article className="metric">
              <span className="metric__label">Entries</span>
              <div className="metric__value">{patient.entry_count}</div>
            </article>
          </div>

          {/* Safety strip: allergies + active conditions */}
          <div className="grid-2" style={{ marginTop: "1.5rem" }}>
            <div className="card">
              <div className="card__title" style={{ color: "var(--danger)" }}>Critical allergies</div>
              {allergies.length === 0 ? (
                <p style={{ margin: 0, color: "var(--ink-soft)", fontSize: "0.9rem" }}>No documented clinical allergies.</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--ink)" }}>
                  {allergies.map((a) => (
                    <li key={a.substance_en} style={{ marginBottom: "0.4rem", fontSize: "0.9rem" }}>
                      <strong>{a.substance_en}</strong>{a.substance_np ? ` (${a.substance_np})` : ""}
                      {a.severity ? ` — <em>${a.severity}</em>` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="card">
              <div className="card__title" style={{ color: "var(--brand)" }}>Active conditions</div>
              {activeConditions.length === 0 ? (
                <p style={{ margin: 0, color: "var(--ink-soft)", fontSize: "0.9rem" }}>No active chronic conditions asserted.</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--ink)" }}>
                  {activeConditions.map((c) => (
                    <li key={c.concept_id} style={{ marginBottom: "0.4rem", fontSize: "0.9rem" }}>
                      <strong>{c.canonical_en}</strong> ({c.canonical_np})
                      {c.icd11_code ? ` · ICD-11: ${c.icd11_code}` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Timeline */}
          <div style={{ marginTop: "1.5rem" }}>
            <div className="card__title" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span>Clinical timeline</span>
              {qrPayload && (
                <button
                  onClick={() => {
                    const b64 = qrPayload.qr_png?.split(",")[1] ?? "";
                    if (!b64) return;
                    const link = document.createElement("a");
                    link.href = `data:image/png;base64,${b64}`;
                    link.download = `swasthyasanjaal_qr_${id}.png`;
                    link.click();
                  }}
                  className="button button--ghost"
                  style={{ fontSize: "0.85rem", padding: "0.35rem 0.7rem" }}
                  disabled={!qrPayload?.qr_png}
                >
                  Download QR
                </button>
              )}
            </div>

            {!entries || entries.length === 0 ? (
              <div className="empty-state" style={{ padding: "2rem 1rem" }}>
                <div className="empty-state__icon">📋</div>
                <div className="empty-state__title">No clinical entries yet</div>
                <p className="empty-state__desc">Use document intake to add a new record for this patient.</p>
              </div>
            ) : (
              <div className="timeline">
                {entries.map((e) => (
                  <div key={e.id} className="timeline-item">
                    <div className="timeline-item__top">
                      <span className="timeline-item__label">{e.document_class?.replace(/_/g, " ") || "Entry"}</span>
                      <span className={`tag ${e.negated_count > 0 ? "tag--negated" : "tag--committed"}`}>
                        {e.negated_count > 0 ? `${e.negated_count} negated` : "Committed"}
                      </span>
                    </div>
                    <p className="timeline-item__summary">{e.summary_np}</p>
                    <div className="review-meta">
                      <span>{e.record_date}</span>
                      <span>{e.input_type.toUpperCase()}</span>
                      <span>{e.concept_count} concepts</span>
                      {e.has_asset && <span>Has asset</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Export utilities */}
          <hr style={{ margin: "2rem 0" }} />
          <div className="card" style={{ marginTop: "1rem" }}>
            <div className="card__title">Record exports</div>
            <div className="actions" style={{ flexWrap: "wrap" }}>
              <button
                onClick={async () => {
                  const blob = await downloadPatientPdf(id);
                  if (!blob) {
                    alert("Unable to generate PDF summary.");
                    return;
                  }
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `swasthyasanjaal_summary_${id}.pdf`;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  URL.revokeObjectURL(url);
                }}
                className="button button--primary"
              >
                📄 Download doctor-summary PDF
              </button>
              <button
                onClick={async () => {
                  const fhir = await fetchPatientFhir(id);
                  if (!fhir) {
                    alert("Unable to generate FHIR bundle.");
                    return;
                  }
                  const blob = new Blob([JSON.stringify(fhir, null, 2)], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `swasthyasanjaal_fhir_${id}.json`;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  URL.revokeObjectURL(url);
                }}
                className="button button--secondary"
              >
                🔗 Export FHIR R4 (JSON)
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
