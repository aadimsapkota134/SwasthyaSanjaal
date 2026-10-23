"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export const dynamic = "force-dynamic";

export default function LoginPage() {
  const router = useRouter();
  const [portal, setPortal] = useState<"individual" | "provider">("individual");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const success = await login(email, password);
      if (success) {
        // Enforce portal matching
        const userJson = localStorage.getItem("swasthya_user");
        if (userJson) {
          const user = JSON.parse(userJson);
          if (portal === "individual" && user.role !== "individual") {
            setError(
              "This account is registered as a Healthcare Provider. Please select 'Healthcare Provider' above to sign in."
            );
            setIsLoading(false);
            return;
          }
          if (
            portal === "provider" &&
            user.role !== "clinician" &&
            user.role !== "administrator"
          ) {
            setError(
              "This account is registered as an Individual. Please select 'Individual' above to sign in."
            );
            setIsLoading(false);
            return;
          }
        }
        router.push("/");
      } else {
        setError("Invalid email or password. Please try again.");
      }
    } catch {
      setError("An unexpected error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center bg-[#f1f5f9] p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-md border border-[#e2e8f0] p-8">
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-[#0f6b54] rounded-2xl flex items-center justify-center mx-auto mb-4">
              <span className="text-white font-bold text-2xl">SS</span>
            </div>
            <h1 className="text-2xl font-bold text-[#0f172a]">Welcome back</h1>
            <p className="text-[#475569] mt-2">
              Select your portal to continue.
            </p>
          </div>

          {/* Portal Switcher */}
          <div className="grid grid-cols-2 gap-2 mb-6 p-1 bg-[#f1f5f9] rounded-xl border border-[#e2e8f0]">
            <button
              type="button"
              onClick={() => {
                setPortal("individual");
                setError("");
              }}
              className={`py-2 px-3 text-xs font-semibold rounded-lg transition-all ${
                portal === "individual"
                  ? "bg-white text-[#0f6b54] shadow-sm font-bold"
                  : "text-[#64748b] hover:text-[#0f172a]"
              }`}
            >
              👤 Individual Portal
            </button>
            <button
              type="button"
              onClick={() => {
                setPortal("provider");
                setError("");
              }}
              className={`py-2 px-3 text-xs font-semibold rounded-lg transition-all ${
                portal === "provider"
                  ? "bg-white text-[#0f6b54] shadow-sm font-bold"
                  : "text-[#64748b] hover:text-[#0f172a]"
              }`}
            >
              🏥 Healthcare Provider
            </button>
          </div>

          {error && (
            <div className="mb-6 p-3 bg-[#fef2f2] border border-[#fecaca] rounded-lg text-[#b91c1c] text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-[#0f172a] mb-1">
                Email
              </label>
              <input
                type="email"
                className="w-full px-4 py-2 border border-[#e2e8f0] rounded-lg focus:ring-2 focus:ring-[#0f6b54] focus:border-transparent outline-none"
                placeholder="you@clinic.org"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-[#0f172a] mb-1">
                Password
              </label>
              <input
                type="password"
                className="w-full px-4 py-2 border border-[#e2e8f0] rounded-lg focus:ring-2 focus:ring-[#0f6b54] focus:border-transparent outline-none"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 bg-[#0f6b54] hover:bg-[#0d5a48] text-white font-semibold rounded-xl disabled:opacity-60 transition-colors shadow-sm text-sm"
            >
              {isLoading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          {/* Quick Demo Access */}
          <div className="mt-6 pt-5 border-t border-[#e2e8f0]">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#64748b] text-center mb-2.5">
              Testing or Evaluation?
            </p>
            <button
              type="button"
              onClick={() => {
                setEmail("admin@swasthya.example");
                setPassword("AdminPass123!");
              }}
              className="w-full py-2.5 px-3 bg-[#f8fafc] hover:bg-[#f1f5f9] text-[#0f6b54] border border-[#cbd5e1] font-medium rounded-xl text-xs transition-colors flex items-center justify-center gap-1.5"
            >
              <span>⚡</span> Autofill Seed Demo Administrator
            </button>
          </div>

          <div className="mt-6 pt-4 border-t border-[#e2e8f0] text-center space-y-2.5">
            <p className="text-sm text-[#475569]">
              Don&#39;t have an account?{" "}
              <Link href="/signup" className="text-[#0f6b54] font-semibold hover:underline">
                Create an account (Sign up)
              </Link>
            </p>
            <div>
              <Link href="/" className="text-xs text-[#64748b] hover:text-[#0f172a]">
                ← Return to dashboard overview
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
