"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchHealth, fetchPatients } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { PatientDetail, PatientSummary, RecordEntrySummary } from "@/lib/contracts";

type HealthService = { service: string; status: string; detail?: string };

export default function DashboardPage() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const [health, setHealth] = useState<{
    status: string;
    model_backend: string;
    model: string;
    services?: HealthService[];
  } | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [myPatient, setMyPatient] = useState<PatientDetail | null>(null);
  const [myReports, setMyReports] = useState<RecordEntrySummary[]>([]);
  const [patientsError, setPatientsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    // Fetch backend connection status for everyone (guest & logged-in)
    fetchHealth()
      .then((h) => {
        if (!cancelled) setHealth(h);
      })
      .catch((e) => {
        if (!cancelled)
          setHealthError(
            e instanceof Error ? e.message : "Unable to reach backend"
          );
      });

    // If authenticated, fetch appropriate data depending on role
    if (isAuthenticated) {
      setLoading(true);
      if (user?.role === "individual") {
        import("@/lib/api").then(({ fetchMyPatient, fetchMyReports }) => {
          Promise.all([fetchMyPatient(), fetchMyReports()])
            .then(([pat, reps]) => {
              if (!cancelled) {
                if (pat) {
                  setMyPatient(pat);
                  setMyReports(reps || []);
                } else {
                  setPatientsError("No personal health record linked to this account.");
                }
              }
            })
            .catch((e) => {
              if (!cancelled)
                setPatientsError(
                  e instanceof Error ? e.message : "Unable to load personal health record"
                );
            })
            .finally(() => {
              if (!cancelled) setLoading(false);
            });
        });
      } else {
        fetchPatients()
          .then((p) => {
            if (!cancelled) {
              if (p === null) {
                setPatientsError("Unable to load patients. Please log in again.");
              } else {
                setPatients(p);
              }
            }
          })
          .catch((e) => {
            if (!cancelled)
              setPatientsError(
                e instanceof Error ? e.message : "Unable to load patients"
              );
          })
          .finally(() => {
            if (!cancelled) setLoading(false);
          });
      }
    } else {
      if (!cancelled) setLoading(false);
    }

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  if (authLoading || (isAuthenticated && loading)) {
    return (
      <div className="page">
        <div
          className="card panel__inner"
          style={{ padding: "3rem 1rem", textAlign: "center" }}
        >
          <p style={{ color: "var(--ink-soft)" }}>Loading…</p>
        </div>
      </div>
    );
  }

  const backendOnline = health?.status === "ok";

  return (
    <div className="page">
      <section className="panel panel--paper">
        <div className="panel__inner">
          {/* Header branding */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 14,
              marginBottom: 16,
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 16,
                  background: "#0f6b54",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 800,
                  fontSize: "1.4rem",
                  boxShadow: "0 4px 12px rgba(15, 107, 84, 0.25)",
                }}
              >
                SS
              </div>
              <div>
                <span className="eyebrow" style={{ margin: 0 }}>
                  Swasthya Sanjaal
                </span>
                <div
                  style={{
                    fontSize: "1.35rem",
                    fontWeight: 800,
                    color: "var(--ink)",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginTop: 2,
                  }}
                >
                  स्वास्थ्य सञ्जाल
                  {isAuthenticated && (
                    <span className="tag tag--committed">Synthetic demo data</span>
                  )}
                </div>
              </div>
            </div>

            {/* Quick auth status badge */}
            <div>
              {isAuthenticated ? (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    background: "#ecfdf5",
                    border: "1px solid #a7f3d0",
                    padding: "6px 12px",
                    borderRadius: 12,
                    fontSize: "0.85rem",
                  }}
                >
                  <span style={{ fontSize: "1rem" }}>👤</span>
                  <span style={{ fontWeight: 600, color: "#065f46" }}>
                    {user?.full_name || user?.email}
                  </span>
                  <span
                    className="tag tag--neutral"
                    style={{ textTransform: "capitalize", fontSize: "0.7rem" }}
                  >
                    {user?.role || "user"}
                  </span>
                </div>
              ) : (
                <div style={{ display: "flex", gap: 8 }}>
                  <Link
                    href="/login"
                    className="button button--secondary"
                    style={{ fontSize: "0.85rem", padding: "0.45rem 0.9rem" }}
                  >
                    Sign in
                  </Link>
                  <Link
                    href="/signup"
                    className="button button--primary"
                    style={{ fontSize: "0.85rem", padding: "0.45rem 0.9rem" }}
                  >
                    Create Account
                  </Link>
                </div>
              )}
            </div>
          </div>

          <h1 className="title">Nepali Clinical Health Ledger</h1>
          <p className="lede">
            Convert Nepali clinical input — prescriptions, lab reports, and notes — into
            reviewed, longitudinal patient records. All writes require explicit human approval.
          </p>

          {/* Guest welcome banner when not authenticated */}
          {!isAuthenticated && (
            <div
              className="card"
              style={{
                marginTop: "1.25rem",
                background: "linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%)",
                borderColor: "#bbf7d0",
                padding: "1.5rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
                <span style={{ fontSize: "2rem" }}>🏥</span>
                <div style={{ flex: 1 }}>
                  <h2
                    style={{
                      fontSize: "1.1rem",
                      fontWeight: 700,
                      color: "#065f46",
                      margin: "0 0 0.4rem 0",
                    }}
                  >
                    Welcome! Anyone can register and explore the platform.
                  </h2>
                  <p
                    style={{
                      fontSize: "0.9rem",
                      color: "#166534",
                      margin: "0 0 1rem 0",
                      lineHeight: 1.5,
                    }}
                  >
                    Whether you are an individual managing personal health summaries or a
                    healthcare clinician processing doctor prescriptions, Swasthya Sanjaal lets
                    you ingest documents, normalize medical terminology, and maintain FHIR R4
                    clinical timelines.
                  </p>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <Link
                      href="/signup"
                      className="button button--primary"
                      style={{ fontSize: "0.85rem", padding: "0.5rem 1.1rem" }}
                    >
                      🚀 Create Free Account (Sign up)
                    </Link>
                    <Link
                      href="/login"
                      className="button button--secondary"
                      style={{ fontSize: "0.85rem", padding: "0.5rem 1.1rem" }}
                    >
                      Sign In to Existing Account
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Connection status */}
          <div className="card" style={{ marginTop: "1.25rem" }}>
            <div className="card__title">Backend connection</div>
            {healthError ? (
              <div className="alert alert--error">
                Unable to reach the backend: {healthError}. Make sure the FastAPI server is
                running on <code style={{ color: "var(--brand)" }}>http://localhost:8000</code>.
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
                <span className={`status-badge ${backendOnline ? "status-ok" : "status-down"}`}>
                  {backendOnline ? "Online" : "Offline"}
                </span>
                <span style={{ fontSize: "0.9rem", color: "var(--ink-soft)" }}>
                  {health?.model_backend} · {health?.model}
                </span>
                {health?.services && health.services.length > 0 && (
                  <span style={{ fontSize: "0.85rem", color: "var(--ink-soft)" }}>
                    {health.services.map((s) => `${s.service}: ${s.status}`).join(" · ")}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Patient Ledger Section */}
          <div style={{ marginTop: "1.5rem" }}>
            <div
              className="card__title"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 8,
              }}
            >
              <span>
                {isAuthenticated
                  ? user?.role === "individual"
                    ? "My Personal Health Summary"
                    : "Your Patients"
                  : "Demonstration Patients Ledger"}
              </span>
              {isAuthenticated && (
                user?.role === "individual" ? (
                  <Link
                    href="/my-reports"
                    className="button button--primary"
                    style={{ fontSize: "0.85rem", padding: "0.4rem 0.85rem" }}
                  >
                    📄 Manage My Reports
                  </Link>
                ) : (
                  <Link
                    href="/intake"
                    className="button button--secondary"
                    style={{ fontSize: "0.85rem", padding: "0.4rem 0.85rem" }}
                  >
                    New intake
                  </Link>
                )
              )}
            </div>

            {!isAuthenticated ? (
              /* Public / Guest Demo Preview */
              <div className="grid-2">
                <div
                  className="card"
                  style={{
                    border: "1px dashed var(--line)",
                    background: "#f8fafc",
                    padding: "1.25rem",
                  }}
                >
                  <div
                    style={{
                      fontSize: "1rem",
                      fontWeight: 700,
                      color: "var(--ink)",
                      marginBottom: "0.25rem",
                    }}
                  >
                    Ram Bahadur Shrestha (राम बहादुर श्रेष्ठ)
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--ink-soft)", marginBottom: "0.5rem" }}>
                    SS-NP-8841 · B+ · Kavrepalanchok
                  </div>
                  <p style={{ fontSize: "0.85rem", color: "var(--ink-soft)", margin: "0.5rem 0" }}>
                    Chronic hypertension and asthma management timeline with synthetic lab reports and prescription OCR.
                  </p>
                  <Link
                    href="/login"
                    className="button button--ghost"
                    style={{ fontSize: "0.85rem", padding: "0.35rem 0.75rem", marginTop: "0.5rem" }}
                  >
                    Sign in to view record →
                  </Link>
                </div>

                <div
                  className="card"
                  style={{
                    border: "1px dashed var(--line)",
                    background: "#f8fafc",
                    padding: "1.25rem",
                  }}
                >
                  <div
                    style={{
                      fontSize: "1rem",
                      fontWeight: 700,
                      color: "var(--ink)",
                      marginBottom: "0.25rem",
                    }}
                  >
                    Gita Sharma (गीता शर्मा)
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--ink-soft)", marginBottom: "0.5rem" }}>
                    SS-NP-2309 · A+ · Lalitpur
                  </div>
                  <p style={{ fontSize: "0.85rem", color: "var(--ink-soft)", margin: "0.5rem 0" }}>
                    Longitudinal prenatal visits, ultrasound notes, and iron supplement prescriptions.
                  </p>
                  <Link
                    href="/login"
                    className="button button--ghost"
                    style={{ fontSize: "0.85rem", padding: "0.35rem 0.75rem", marginTop: "0.5rem" }}
                  >
                    Sign in to view record →
                  </Link>
                </div>
              </div>
            ) : patientsError ? (
              <div className="alert alert--error">
                Unable to load records: {patientsError}
              </div>
            ) : user?.role === "individual" ? (
              /* Individual Minimal Patient-Focused Dashboard */
              <div>
                {myPatient ? (
                  <div
                    className="card"
                    style={{
                      border: "2px solid #a7f3d0",
                      background: "linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%)",
                      padding: "1.75rem",
                      borderRadius: 16,
                      boxShadow: "0 4px 16px rgba(15, 107, 84, 0.08)",
                      marginBottom: "1.5rem",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        flexWrap: "wrap",
                        gap: 12,
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontSize: "1.3rem",
                            fontWeight: 800,
                            color: "var(--ink)",
                          }}
                        >
                          {myPatient.name_np ? `${myPatient.name} (${myPatient.name_np})` : myPatient.name}
                        </div>
                        <div
                          style={{
                            fontSize: "0.9rem",
                            color: "var(--brand)",
                            fontWeight: 600,
                            marginTop: 4,
                          }}
                        >
                          {myPatient.sanjaal_id} · Blood Group: {myPatient.blood_group || "—"}
                        </div>
                      </div>
                      <Link
                        href="/my-reports"
                        className="button button--primary"
                        style={{ fontSize: "0.85rem", padding: "0.45rem 1rem" }}
                      >
                        ⚡ Generate Pre-Visit Report
                      </Link>
                    </div>

                    {/* Personal Health Metrics */}
                    <div className="metrics" style={{ marginTop: "1.25rem", gap: "0.75rem" }}>
                      <article className="metric" style={{ padding: "0.75rem" }}>
                        <span className="metric__label">Personal Reports</span>
                        <div className="metric__value">{myReports.length}</div>
                      </article>
                      <article className="metric" style={{ padding: "0.75rem" }}>
                        <span className="metric__label">Active Conditions</span>
                        <div className="metric__value">{myPatient.conditions?.length || 0}</div>
                      </article>
                      <article className="metric" style={{ padding: "0.75rem" }}>
                        <span className="metric__label">Documented Allergies</span>
                        <div className="metric__value">{myPatient.allergies?.length || 0}</div>
                      </article>
                    </div>

                    {/* Pre-Visit Report Generator Banner */}
                    <div
                      style={{
                        marginTop: "1.25rem",
                        padding: "1rem",
                        background: "#ffffff",
                        border: "1px solid #d1fae5",
                        borderRadius: 12,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 12,
                        flexWrap: "wrap",
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700, color: "#065f46", fontSize: "0.95rem" }}>
                          🏥 Visiting a doctor or health post soon?
                        </div>
                        <div style={{ fontSize: "0.85rem", color: "#475569", marginTop: 2 }}>
                          Prepare a concise, plain-Nepali doctor visit summary from your latest prescriptions and lab reports.
                        </div>
                      </div>
                      <Link
                        href="/my-reports"
                        className="button button--secondary"
                        style={{ fontSize: "0.85rem", padding: "0.4rem 0.9rem" }}
                      >
                        Upload & Summarize →
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="empty-state">
                    <div className="empty-state__icon">📄</div>
                    <div className="empty-state__title">Setting up your health profile</div>
                    <p className="empty-state__desc">
                      Your personal record is ready to receive documents.
                    </p>
                  </div>
                )}
              </div>
            ) : !patients || patients.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state__icon">👥</div>
                <div className="empty-state__title">No patients assigned</div>
                <p className="empty-state__desc">
                  No patient records have been assigned to your account yet. You can submit a new
                  document intake to create your first record.
                </p>
                <Link
                  href="/intake"
                  className="button button--primary"
                  style={{ marginTop: "1rem", fontSize: "0.85rem" }}
                >
                  Start first intake
                </Link>
              </div>
            ) : (
              <div className="grid-2">
                {patients.map((p) => (
                  <Link
                    key={p.id}
                    href={`/patients/${p.id}`}
                    className="card"
                    style={{
                      textDecoration: "none",
                      color: "inherit",
                      display: "block",
                      transition: "transform 0.15s ease, box-shadow 0.15s ease",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "1rem",
                        fontWeight: 700,
                        color: "var(--ink)",
                        marginBottom: "0.25rem",
                      }}
                    >
                      {p.name_np ? `${p.name} (${p.name_np})` : p.name}
                    </div>
                    <div style={{ fontSize: "0.85rem", color: "var(--ink-soft)", marginBottom: "0.5rem" }}>
                      {p.sanjaal_id} · {p.blood_group || "Unknown blood group"} · {p.district || "—"}
                    </div>
                    <div className="metrics" style={{ marginTop: "0.75rem", gap: "0.5rem" }}>
                      <article className="metric" style={{ padding: "0.6rem" }}>
                        <span className="metric__label">Entries</span>
                        <div className="metric__value">{p.entry_count}</div>
                      </article>
                      <article className="metric" style={{ padding: "0.6rem" }}>
                        <span className="metric__label">Gender</span>
                        <div className="metric__value">{p.gender_np || p.gender || "—"}</div>
                      </article>
                    </div>
                    <div
                      style={{
                        marginTop: "0.75rem",
                        fontSize: "0.85rem",
                        color: "var(--brand)",
                        fontWeight: 600,
                      }}
                    >
                      Open record →
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {isAuthenticated && (
            <div
              style={{
                marginTop: "2rem",
                paddingTop: "1rem",
                borderTop: "1px solid var(--line)",
              }}
            >
              <p style={{ fontSize: "0.85rem", color: "var(--ink-soft)", margin: 0 }}>
                ⚠️ This is a demonstration system using synthetic patient data. No real patient
                information is stored. Self-registration is enabled for individuals and clinicians.
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
