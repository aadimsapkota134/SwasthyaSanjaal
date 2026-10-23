"use client";

import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import SignupPage from "./page";

jest.mock("@/lib/auth-context", () => ({
  useAuth: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
const mockUseRouter = useRouter as jest.MockedFunction<typeof useRouter>;
const mockRouterPush = jest.fn();
const mockSignup = jest.fn();

describe("SignupPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseRouter.mockReturnValue({ push: mockRouterPush } as unknown as ReturnType<typeof useRouter>);
    mockUseAuth.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: jest.fn(),
      signup: mockSignup,
      logout: jest.fn(),
      refreshUser: jest.fn(),
    });
  });

  it("renders all form fields and role selector", async () => {
    await act(async () => {
      render(<SignupPage />);
    });

    expect(screen.getByText(/Create your account/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/Sita Thapa/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/you@domain.com/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/At least 8 characters/i)).toBeTruthy();
    expect(screen.getByText(/Individual/i)).toBeTruthy();
    expect(screen.getByText(/Healthcare Provider/i)).toBeTruthy();
  });

  it("validates short password client-side", async () => {
    await act(async () => {
      render(<SignupPage />);
    });

    fireEvent.change(screen.getByPlaceholderText(/Sita Thapa/i), { target: { value: "Sita" } });
    fireEvent.change(screen.getByPlaceholderText(/you@domain.com/i), { target: { value: "sita@test.com" } });
    fireEvent.change(screen.getByPlaceholderText(/At least 8 characters/i), { target: { value: "short" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });

    expect(screen.getByText(/Password must be at least 8 characters long/i)).toBeTruthy();
    expect(mockSignup).not.toHaveBeenCalled();
  });

  it("calls signup and redirects to dashboard on success", async () => {
    mockSignup.mockResolvedValueOnce(true);

    await act(async () => {
      render(<SignupPage />);
    });

    fireEvent.change(screen.getByPlaceholderText(/Sita Thapa/i), { target: { value: "Sita Thapa" } });
    fireEvent.change(screen.getByPlaceholderText(/you@domain.com/i), { target: { value: "sita@test.com" } });
    fireEvent.change(screen.getByPlaceholderText(/At least 8 characters/i), { target: { value: "SecretPass123!" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });

    await waitFor(() => {
      expect(mockSignup).toHaveBeenCalledWith("sita@test.com", "SecretPass123!", "Sita Thapa", "individual");
      expect(mockRouterPush).toHaveBeenCalledWith("/");
    });
  });

  it("displays error message when signup fails", async () => {
    mockSignup.mockResolvedValueOnce(false);

    await act(async () => {
      render(<SignupPage />);
    });

    fireEvent.change(screen.getByPlaceholderText(/Sita Thapa/i), { target: { value: "Sita Thapa" } });
    fireEvent.change(screen.getByPlaceholderText(/you@domain.com/i), { target: { value: "existing@test.com" } });
    fireEvent.change(screen.getByPlaceholderText(/At least 8 characters/i), { target: { value: "SecretPass123!" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/Unable to create account/i)).toBeTruthy();
    });
  });
});
