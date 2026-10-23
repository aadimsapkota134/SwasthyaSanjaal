"use client";

import { fetchPatients, fetchHealth } from "./api";
import type { PatientSummary } from "./contracts";

// Mock fetch globally for jsdom environment
const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
globalThis.fetch = mockFetch;

beforeEach(() => {
  jest.clearAllMocks();
  mockFetch.mockReset();
});

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

    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(mockPatients), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

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
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const result = await fetchPatients();
    expect(result).toEqual([]);
  });

  it("returns null on non-OK response (e.g., 401 unauthorized)", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      })
    );

    const result = await fetchPatients();
    expect(result).toBeNull();
  });

  it("returns null on malformed JSON response", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response("not json", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

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

    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(mockHealth), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const result = await fetchHealth();
    expect(result).toEqual(mockHealth);
  });

  it("returns null on non-OK response", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Internal Server Error" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      })
    );

    const result = await fetchHealth();
    expect(result).toBeNull();
  });
});
