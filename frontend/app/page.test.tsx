"use client";

import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { fetchPatients, fetchHealth } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import DashboardPage from "./page";
import type { PatientSummary } from "@/lib/contracts";

jest.mock("@/lib/api", () => ({
  fetchHealth: jest.fn(),
  fetchPatients: jest.fn(),
}));

jest.mock("@/lib/auth-context", () => ({
  useAuth: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

const mockFetchPatients = fetchPatients as jest.MockedFunction<typeof fetchPatients>;
const mockFetchHealth = fetchHealth as jest.MockedFunction<typeof fetchHealth>;
const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
const mockUseRouter = useRouter as jest.MockedFunction<typeof useRouter>;
const mockRouterPush = jest.fn();

const mockPatient: PatientSummary = {
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
};

const mockHealth = {
  status: "ok",
  service: "swasthyasanjaal-api",
  model_backend: "cloud",
  model: "gemma4:31b-cloud",
  services: [
    { service: "db", status: "up" },
    { service: "primary_model", status: "up" },
    { service: "fallback_model", status: "down", detail: "ConnectError" },
  ],
};

const mockUser = {
  user_id: "user1",
  email: "admin@test.com",
  role: "administrator",
  full_name: "Admin User",
  is_active: true,
  created_at: "2026-10-23T00:00:00Z",
};

describe("DashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseRouter.mockReturnValue({ push: mockRouterPush } as unknown as ReturnType<typeof useRouter>);
    mockFetchHealth.mockResolvedValue(mockHealth);
    mockFetchPatients.mockResolvedValue([mockPatient]);
  });

  it("renders loading state initially", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      login: jest.fn(),
      logout: jest.fn(),
      refreshUser: jest.fn(),
    });

    render(<DashboardPage />);
    expect(screen.getByText(/loading…/i)).toBeTruthy();
  });

  it("redirects to login when not authenticated", async () => {
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
      refreshUser: jest.fn(),
    });

    mockRouterPush.mockReset();

    render(<DashboardPage />);
    await waitFor(() => {
      expect(mockRouterPush).toHaveBeenCalledWith("/login");
    });
  });

  it("renders patient cards when patients are loaded", async () => {
    mockUseAuth.mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
      refreshUser: jest.fn(),
    });

    await act(async () => {
      render(<DashboardPage />);
    });
    await waitFor(() => {
      expect(screen.getByText(/Ram Bahadur Shrestha/)).toBeTruthy();
    });
    expect(screen.getByText(/राम बहादुर श्रेष्ठ/)).toBeTruthy();
    expect(screen.getByText(/B\+/)).toBeTruthy();
  });

  it("renders empty state when no patients are assigned", async () => {
    mockUseAuth.mockReturnValue({
      user: { ...mockUser, role: "clinician" },
      isAuthenticated: true,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
      refreshUser: jest.fn(),
    });

    mockFetchPatients.mockResolvedValueOnce([]);

    await act(async () => {
      render(<DashboardPage />);
    });
    await waitFor(() => {
      screen.getByText(/no patients assigned/i);
    });
  });

  it("renders error state when patients fetch returns null", async () => {
    mockUseAuth.mockReturnValue({
      user: { ...mockUser, role: "clinician" },
      isAuthenticated: true,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
      refreshUser: jest.fn(),
    });

    mockFetchPatients.mockResolvedValueOnce(null);

    await act(async () => {
      render(<DashboardPage />);
    });
    const alert = screen.getByText(/Unable to load patients/);
    expect(alert).toBeTruthy();
    expect(alert.textContent).toContain("Unable to load patients");
  });

  it("renders error state when API throws", async () => {
    mockUseAuth.mockReturnValue({
      user: { ...mockUser, role: "clinician" },
      isAuthenticated: true,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
      refreshUser: jest.fn(),
    });

    mockFetchPatients.mockRejectedValueOnce(new Error("Network error"));

    await act(async () => {
      render(<DashboardPage />);
    });
    const alert = screen.getByText(/Unable to load patients/);
    expect(alert).toBeTruthy();
    expect(alert.textContent).toContain("Unable to load patients");
  });
});
