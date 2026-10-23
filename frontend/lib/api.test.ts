"use client";

import { fetchPatients, fetchHealth, signup } from "./api";
import type { PatientSummary } from "./contracts";

// Mock fetch globally for jsdom environment
const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
Object.defineProperty(globalThis, "fetch", {
  configurable: true,
  writable: true,
  value: mockFetch,
});

beforeEach(() => {
  jest.clearAllMocks();
  mockFetch.mockReset();
});

function mockResponse(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: jest.fn().mockReturnValue(null) },
    json: jest.fn().mockResolvedValue(data),
  } as unknown as Response;
}

describe("fetchPatients", () => {
  it("returns patient list on successful response", async () => {
    const mockPatients: PatientSummary[] = [
      {
        id: "patient_ram",
        name: "Ram Bahadur Shrestha",
        name_np: "राम बहादुर श्रेष्ठ",
        sanjaal_id: "SS-NP-8841",
        sanchai_id: "SANCHAI-8841",
        arogya_id: null,
        age: 42,
        gender: "male",
        gender_np: "पुरुष",
        district: "Kavrepalanchok",
        blood_group: "B+",
        entry_count: 4,
      },
    ];

    mockFetch.mockResolvedValueOnce(mockResponse(mockPatients));

    const result = await fetchPatients();
    expect(result).toEqual(mockPatients);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/patients",
      expect.objectContaining({
        credentials: "include",
        cache: "no-store",
      })
    );
  });

  it("returns empty array on empty patient list", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse([]));

    const result = await fetchPatients();
    expect(result).toEqual([]);
  });

  it("returns null on non-OK response (e.g., 401 unauthorized)", async () => {
    mockFetch.mockResolvedValueOnce(mockResponse({ detail: "Authentication required" }, 401));

    const result = await fetchPatients();
    expect(result).toBeNull();
  });

  it("returns null when fetch throws (network error)", async () => {
    mockFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await fetchPatients();
    expect(result).toBeNull();
  });
});

describe("fetchHealth", () => {
  it("returns health data on successful response", async () => {
    const mockHealth = {
      status: "ok",
      service: "swasthyasanjaal-api",
      model: "gemma4:31b-cloud",
      model_backend: "cloud",
      services: [
        { service: "db", status: "up" },
        { service: "primary_model", status: "up" },
        { service: "fallback_model", status: "down", detail: "ConnectError" },
      ],
    };

    mockFetch.mockResolvedValueOnce(mockResponse(mockHealth));

    const result = await fetchHealth();
    expect(result).toEqual(mockHealth);
  });

  it("returns null on non-OK response", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse({ detail: "Internal Server Error" }, 500)
    );

    const result = await fetchHealth();
    expect(result).toBeNull();
  });
});

describe("signup", () => {
  it("returns user response on successful registration", async () => {
    const mockSignupResponse = {
      user_id: "user_123",
      email: "new.user@example.com",
      role: "individual",
      expires_at: 1792770000,
    };

    mockFetch.mockResolvedValueOnce(mockResponse(mockSignupResponse, 201));

    const result = await signup(
      "new.user@example.com",
      "SecurePass123!",
      "New User",
      "individual"
    );
    expect(result).not.toBeNull();
    expect(result?.user.email).toBe("new.user@example.com");
    expect(result?.user.role).toBe("individual");
  });

  it("returns null on conflict or failed registration", async () => {
    mockFetch.mockResolvedValueOnce(
      mockResponse(
        { detail: "An account with this email address already exists" },
        409
      )
    );

    const result = await signup("existing@example.com", "SecurePass123!");
    expect(result).toBeNull();
  });
});
