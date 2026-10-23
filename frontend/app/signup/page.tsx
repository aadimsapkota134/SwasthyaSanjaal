"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export const dynamic = "force-dynamic";

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"individual" | "clinician">("individual");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setIsLoading(true);
    try {
      const success = await signup(email, password, fullName, role);
      if (success) {
        router.push("/");
      } else {
        setError(
          "Unable to create account. The email may already be in use or the password is too common."
        );
      }
    } catch {
      setError("An unexpected error occurred during signup. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center bg-[#f8fafc] p-4">
      <div className="w-full max-w-lg">
        <div className="bg-white rounded-2xl shadow-sm border border-[#e2e8f0] p-6 sm:p-8">
          <div className="text-center mb-6">
            <div className="w-16 h-16 bg-[#0f6b54] rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-md">
              <span className="text-white font-extrabold text-2xl tracking-wide">SS</span>
            </div>
            <h1 className="text-2xl font-bold text-[#0f172a]">Create your account</h1>
            <p className="text-[#475569] text-sm mt-1">
              Join Swasthya Sanjaal — Nepali Clinical Health Ledger
            </p>
          </div>

          {error && (
            <div className="mb-5 p-3.5 bg-[#fef2f2] border border-[#fecaca] rounded-xl text-[#b91c1c] text-sm flex items-start gap-2">
              <span className="text-base leading-none">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Account Type Selector */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[#475569] mb-2">
                Account Type
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setRole("individual")}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    role === "individual"
                      ? "border-[#0f6b54] bg-[#ecfdf5] shadow-xs"
                      : "border-[#e2e8f0] bg-white hover:border-[#cbd5e1]"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">👤</span>
                    <span className="font-semibold text-sm text-[#0f172a]">Individual</span>
                  </div>
                  <p className="text-xs text-[#64748b]">
                    Personal access, medical history, and clinical summaries
                  </p>
                </button>

                <button
                  type="button"
                  onClick={() => setRole("clinician")}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    role === "clinician"
                      ? "border-[#0f6b54] bg-[#ecfdf5] shadow-xs"
                      : "border-[#e2e8f0] bg-white hover:border-[#cbd5e1]"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">🩺</span>
                    <span className="font-semibold text-sm text-[#0f172a]">Healthcare Provider</span>
                  </div>
                  <p className="text-xs text-[#64748b]">
                    Prescription OCR, clinical intake, and ledger approval
                  </p>
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-[#0f172a] mb-1">
                Full Name
              </label>
              <input
                type="text"
                className="w-full px-3.5 py-2.5 border border-[#e2e8f0] rounded-xl focus:ring-2 focus:ring-[#0f6b54] focus:border-transparent outline-none text-sm transition-all"
                placeholder="e.g. Sita Thapa or Dr. Ramesh Sharma"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-[#0f172a] mb-1">
                Email Address
              </label>
              <input
                type="email"
                className="w-full px-3.5 py-2.5 border border-[#e2e8f0] rounded-xl focus:ring-2 focus:ring-[#0f6b54] focus:border-transparent outline-none text-sm transition-all"
                placeholder="you@domain.com"
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
                className="w-full px-3.5 py-2.5 border border-[#e2e8f0] rounded-xl focus:ring-2 focus:ring-[#0f6b54] focus:border-transparent outline-none text-sm transition-all"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
              <p className="text-xs text-[#64748b] mt-1">
                Must be at least 8 characters and avoid common words.
              </p>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 py-3 px-4 bg-[#0f6b54] hover:bg-[#0d5a48] text-white font-semibold rounded-xl disabled:opacity-60 transition-colors shadow-sm text-sm"
            >
              {isLoading ? "Creating account…" : "Create account & Start using app"}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-[#e2e8f0] text-center space-y-2">
            <p className="text-sm text-[#475569]">
              Already have an account?{" "}
              <Link href="/login" className="text-[#0f6b54] font-semibold hover:underline">
                Sign in
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
