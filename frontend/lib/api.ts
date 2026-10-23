"use client";

import type {
  CreateUserRequest,
  EvalRunResponse,
  FhirBundle,
  IntakeResponse,
  PatientDetail,
  PatientSummary,
  QrPayload,
  RecordEntryDetail,
  RecordEntrySummary,
  UpdateUserRequest,
  UserResponse,
} from "@/lib/contracts";

type DashboardPayload = {
  patient: PatientDetail;
  entries: RecordEntrySummary[];
  intake: IntakeResponse;
};

const FALLBACK_API_BASE_URL = "http://localhost:8000";

function getApiBaseUrl() {
  const configured =
    typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_BASE_URL
      ? process.env.NEXT_PUBLIC_API_BASE_URL.trim()
      : undefined;
  if (configured) {
    return configured.replace(/\/api\/v1\/?$/, "").replace(/\/+$/, "");
  }
  return FALLBACK_API_BASE_URL;
}

async function safeJson<T>(response: Response): Promise<T | null> {
  if (!response.ok) {
    return null;
  }
  try {
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

async function fetchJson<T>(
  path: string,
  options?: RequestInit
): Promise<T | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    return await safeJson<T>(response);
  } catch {
    return null;
  }
}

// ---- Auth ----

export async function login(
  email: string,
  password: string
): Promise<{ user: UserResponse; csrfToken: string | null } | null> {  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) {
      return null;
    }
    const body = (await response.json()) as {
      user_id: string;
      email: string;
      role: string;
      expires_at: number;
    };
    const csrfToken =
      response.headers?.get?.("set-cookie")?.match(/csrf_token=([^;]+)/)?.[1] ?? null;
    return {
      user: {
        user_id: body.user_id,
        email: body.email,
        full_name: null,
        role: body.role,
        is_active: true,
        created_at: "",
      },
      csrfToken,
    };
  } catch {
    return null;
  }
}

export async function signup(
  email: string,
  password: string,
  fullName?: string,
  role: "individual" | "clinician" = "individual"
): Promise<{ user: UserResponse; csrfToken: string | null }> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      email,
      password,
      full_name: fullName?.trim() || null,
      role,
    }),
  });
  if (!response.ok) {
    let detail = "Unable to create account. Please try again.";
    try {
      const errBody = (await response.json()) as { detail?: string };
      if (errBody.detail) detail = errBody.detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }
  const body = (await response.json()) as {
    user_id: string;
    email: string;
    role: string;
    expires_at: number;
  };
  const csrfToken =
    response.headers?.get?.("set-cookie")?.match(/csrf_token=([^;]+)/)?.[1] ?? null;
  return {
    user: {
      user_id: body.user_id,
      email: body.email,
      full_name: fullName?.trim() || null,
      role: body.role,
      is_active: true,
      created_at: "",
    },
    csrfToken,
  };
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${getApiBaseUrl()}/api/v1/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // Ignore errors - logout is best-effort
  }
}

export async function getCurrentUser(): Promise<UserResponse | null> {
  return fetchJson<UserResponse>("/api/v1/auth/me");
}

// ---- Existing API (unchanged, but now with credentials: include) ----

export async function fetchHealth(): Promise<{
  status: string;
  service: string;
  model: string;
  model_backend: string;
  services: Array<{ service: string; status: string; detail?: string }>;
} | null> {
  return fetchJson("/api/v1/health");
}

export async function fetchDashboardData(): Promise<DashboardPayload | null> {
  return fetchJson<DashboardPayload>("/api/v1/dashboard");
}

export async function fetchPatients(): Promise<PatientSummary[] | null> {
  return fetchJson<PatientSummary[]>("/api/v1/patients");
}

export async function fetchPatientById(id: string): Promise<PatientDetail | null> {
  return fetchJson<PatientDetail>(`/api/v1/patients/${id}`);
}

export async function fetchPatientRecord(
  id: string
): Promise<{ patient: PatientDetail; entries: RecordEntrySummary[] } | null> {
  return fetchJson<{ patient: PatientDetail; entries: RecordEntrySummary[] }>(
    `/api/v1/patients/${id}/record`
  );
}

export async function fetchPatientTimeline(
  id: string
): Promise<RecordEntrySummary[] | null> {
  const record = await fetchPatientRecord(id);
  return record ? record.entries : null;
}

export async function fetchEntryById(
  patientId: string,
  entryId: string
): Promise<RecordEntryDetail | null> {
  return fetchJson<RecordEntryDetail>(
    `/api/v1/patients/${patientId}/entries/${entryId}`
  );
}

export async function fetchMyPatient(): Promise<PatientDetail | null> {
  return fetchJson<PatientDetail>("/api/v1/me/patient");
}

export async function fetchMyReports(): Promise<RecordEntryDetail[] | null> {
  return fetchJson<RecordEntryDetail[]>("/api/v1/me/reports");
}

export function getMyReportFileUrl(entryId: string): string {
  return `${getApiBaseUrl()}/api/v1/me/reports/${entryId}/file`;
}

export async function postMyReport(
  payload: Record<string, unknown>
): Promise<RecordEntryDetail | null> {
  return fetchJson<RecordEntryDetail>("/api/v1/me/reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchPatientQr(id: string): Promise<QrPayload | null> {
  return fetchJson<QrPayload>(`/api/v1/patients/${id}/qr`);
}

export async function postIntakeText(
  text: string,
  useModel = false,
  correct = true
): Promise<IntakeResponse | null> {
  return fetchJson<IntakeResponse>("/api/v1/intake/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, use_model: useModel, correct }),
  });
}

export async function postIntakeFile(
  file: File,
  documentClass: string | null = null,
  useModel = false,
  correct = true
): Promise<IntakeResponse | null> {
  const formData = new FormData();
  formData.append("file", file);
  if (documentClass) {
    formData.append("document_class", documentClass);
  }
  formData.append("use_model", String(useModel));
  formData.append("correct", String(correct));

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/intake/ocr`, {
      method: "POST",
      body: formData,
      credentials: "include",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as IntakeResponse;
  } catch {
    return null;
  }
}

export async function postCommitEntry(
  patientId: string,
  payload: Record<string, unknown>
): Promise<RecordEntryDetail | null> {
  return fetchJson<RecordEntryDetail>(
    `/api/v1/patients/${patientId}/entries`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
}

export async function fetchPatientFhir(id: string): Promise<FhirBundle | null> {
  return fetchJson<FhirBundle>(`/api/v1/patients/${id}/fhir`);
}

export async function downloadPatientPdf(id: string): Promise<Blob | null> {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/v1/patients/${id}/summary.pdf`,
      { cache: "no-store", credentials: "include" }
    );
    if (!response.ok) {
      return null;
    }
    return await response.blob();
  } catch {
    return null;
  }
}

export async function fetchLatestEval(): Promise<EvalRunResponse | null> {
  return fetchJson<EvalRunResponse>("/api/v1/eval/latest");
}

export type QrDecodeResult = {
  success: boolean;
  raw_text: string;
  token: string;
  patient_id?: string | null;
  patient_name?: string | null;
  blood_group?: string | null;
  emergency_path: string;
};

export async function decodeQrImage(
  fileOrBlob: File | Blob
): Promise<QrDecodeResult | null> {
  const formData = new FormData();
  formData.append("file", fileOrBlob, "scan.png");
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/v1/qr/decode`, {
      method: "POST",
      body: formData,
      credentials: "include",
    });
    if (!res.ok) return null;
    return (await res.json()) as QrDecodeResult;
  } catch {
    return null;
  }
}

// ---- Admin ----

export async function createUser(
  payload: CreateUserRequest
): Promise<UserResponse | null> {
  return fetchJson<UserResponse>("/api/v1/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listUsers(): Promise<UserResponse[] | null> {
  return fetchJson<UserResponse[]>("/api/v1/admin/users");
}

export async function updateUser(
  userId: string,
  payload: UpdateUserRequest
): Promise<UserResponse | null> {
  return fetchJson<UserResponse>(`/api/v1/admin/users/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function grantPatientAccess(
  payload: { user_id: string; patient_id: string }
): Promise<{
  id: string;
  user_id: string;
  patient_id: string;
  granted_by: string | null;
  granted_at: string;
  revoked_at: string | null;
} | null> {
  return fetchJson("/api/v1/admin/patient-access", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function revokePatientAccess(
  payload: { user_id: string; patient_id: string }
): Promise<null> {
  await fetchJson("/api/v1/admin/patient-access", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return null;
}

export async function listPatientAccess(): Promise<Array<{
  id: string;
  user_id: string;
  patient_id: string;
  granted_by: string | null;
  granted_at: string;
  revoked_at: string | null;
}> | null> {
  return fetchJson("/api/v1/admin/patient-access");
}
