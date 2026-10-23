"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fetchHealth, fetchPatients } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { PatientSummary } from "@/lib/contracts";

type HealthService = { service: string; status: string; detail?: string };

export default function DashboardPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [health, setHealth] = useState<{ status: string; model_backend: string; model: string; services?: HealthService[] } | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [patientsError, setPatientsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }
    if (authLoading || !isAuthenticated) {
      return;
    }

    let cancelled = false;

    queueMicrotask(() => {
      if (!cancelled) setLoading(true);
    });

    fetchHealth().then((h) => {
      if (!cancelled) setHealth(h);
    }).catch((e) => {
      if (!cancelled) setHealthError(e instanceof Error ? e.message : "Unable to reach backend");
    });
    fetchPatients().then((p) => {
      if (!cancelled) {
        if (p === null) {
          setPatientsError("Unable to load patients. Please log in again.");
        } else {
          setPatients(p);
        }
      }
    }).catch((e) => {
      if (!cancelled) setPatientsError(e instanceof Error ? e.message : "Unable to load patients");
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [isAuthenticated, authLoading, router]);

  if (authLoading || loading) {
    return (
      <div className="page">
        <div className="card panel__inner" style={{ padding: "3rem 1rem", textAlign: "center" }}>
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
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14, flexWrap: "wrap" }}>
            <div style={{ width: 48, height: 48, borderRadius: 14, background: "#0f6b54", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: "1.3rem" }}>SS</div>
            <div>
              <span className="eyebrow" style={{ margin: 0 }}>Swasthya Sanjaal</span>
              <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--ink)", display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
                स्वास्थ्य सञ्जाल <span className="tag tag--committed">Synthetic demo data</span>
              </div>
            </div>
          </div>

          <h1 className="title">Clinical Health Ledger</h1>
          <p className="lede">
            Convert Nepali clinical input — prescriptions, lab reports, and notes — into
            reviewed, longitudinal patient records. All writes require explicit human approval.
          </p>

          {/* Connection status */}
          <div className="card" style={{ marginTop: "1.5rem" }}>
            <div className="card__title">Backend connection</div>
            {loading ? (
              <p style={{ color: "var(--ink-soft)", fontSize: "0.9rem" }}>Connecting…</p>
            ) : healthError ? (
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

          {/* Patients */}
          <div style={{ marginTop: "1.5rem" }}>
            <div className="card__title" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span>Patients</span>
              <Link href="/intake" className="button button--secondary" style={{ fontSize: "0.85rem", padding: "0.4rem 0.85rem" }}>
                New intake
              </Link>
            </div>

            {patientsError ? (
              <div className="alert alert--error">
                Unable to load patients: {patientsError}
              </div>
            ) : patients === null ? (
              <div className="empty-state">
                <div className="empty-state__icon">👥</div>
                <div className="empty-state__title">No patients assigned</div>
                <p className="empty-state__desc">No patient records have been assigned to your account. Contact your administrator.</p>
              </div>
            ) : patients.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state__icon">👥</div>
                <div className="empty-state__title">No patients assigned</div>
                <p className="empty-state__desc">No patient records have been assigned to your account. Contact your administrator.</p>
              </div>
            ) : (
              <div className="grid-2">
                {patients.map((p) => (
                  <Link
                    key={p.id}
                    href={`/patients/${p.id}`}
                    className="card"
                    style={{ textDecoration: "none", color: "inherit", display: "block" }}
                  >
                    <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--ink)", marginBottom: "0.25rem" }}>
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
                    <div style={{ marginTop: "0.75rem", fontSize: "0.85rem", color: "var(--brand)", fontWeight: 600 }}>
                      Open record →
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div style={{ marginTop: "1.5rem", paddingTop: "1rem", borderTop: "1px solid var(--line)" }}>
            <p style={{ fontSize: "0.85rem", color: "var(--ink-soft)", margin: 0 }}>
              ⚠️ This is a demonstration system using synthetic patient data. No real patient
              information is stored. Authentication and authorization are enabled — contact your
              administrator for account access.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
