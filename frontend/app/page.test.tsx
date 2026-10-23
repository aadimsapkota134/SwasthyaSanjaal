"use client";

import React from "react";
import { render, screen, act } from "@testing-library/react";
import { fetchPatients, fetchHealth } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import DashboardPage from "./page";

jest.mock("@/lib/api", () => ({
  fetchHealth: jest.fn(),
  fetchPatients: jest.fn(),
}));

jest.mock("@/lib/auth-context", () => ({
  useAuth: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(() => ({ push: jest.fn() })),
}));

const mockFetchPatients = fetchPatients as jest.MockedFunction<typeof fetchPatients>;
const mockFetchHealth = fetchHealth as jest.MockedFunction<typeof fetchHealth>;
const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;

const mockPatient: any = {
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

const mockHealth: any = {
  status: "ok",
  model_backend: "cloud",
  model: "gemma4:31b-cloud",
  services: [
    { service: "db", status: "up" },
    { service: "primary_model", status: "up" },
    { service: "fallback_model", status: "down", detail: "ConnectError" },
  ],
};

describe("DashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Set default return values that persist across calls
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
    expect(screen.getByText(/loading…/i)).toBeInTheDocument();
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

    render(<DashboardPage />);
    await waitFor(() => {
      expect(require("next/navigation").useRouter().push).toHaveBeenCalledWith("/login");
    });
  });

  it("renders patient cards when patients are loaded", async () => {
    mockUseAuth.mockReturnValue({
      user: { user_id: "user1", email: "admin@test.com", role: "administrator" },
      isAuthenticated: true,
      isLoading: false,
      login: jest.fn(),
      logout: jest.fn(),
      refreshUser: jest.fn(),
    });

    await act(async () => {
      render(<DashboardPage />);
    });
    expect(screen.getByText("Ram Bahadur Shrestha")).toBeInTheDocument();
    expect(screen.getByText("राम बहादुर श्रेष्ठ")).toBeInTheDocument();
    expect(screen.getByText("B+")).toBeInTheDocument();
  });

  it("renders empty state when no patients are assigned", async () => {
    mockUseAuth.mockReturnValue({
      user: { user_id: "user1", email: "admin@test.com", role: "clinician" },
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
    expect(screen.getByText(/no patients assigned/i)).toBeInTheDocument();
  });

  it("renders error state when patients fetch returns null", async () => {
    mockUseAuth.mockReturnValue({
      user: { user_id: "user1", email: "admin@test.com", role: "clinician" },
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
    expect(alert).toBeInTheDocument();
    expect(alert.textContent).toContain("Unable to load patients");
  });

  it("renders error state when API throws", async () => {
    mockUseAuth.mockReturnValue({
      user: { user_id: "user1", email: "admin@test.com", role: "clinician" },
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
    expect(alert).toBeInTheDocument();
    expect(alert.textContent).toContain("Unable to load patients");
  });
});
