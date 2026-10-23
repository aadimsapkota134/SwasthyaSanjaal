"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";

export function NavHeader() {
  const { user, logout, isAuthenticated, isLoading } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
  };

  return (
    <header className="nav-header" role="banner">
      <div className="nav-header__inner">
        <Link href="/" className="nav-header__brand" aria-label="Swasthya Sanjaal home">
          <div className="nav-header__mark">SS</div>
          <div className="nav-header__name">
            Swasthya <span>Sanjaal</span>
          </div>
        </Link>

        <nav className="nav-header__nav" aria-label="Main navigation">
          {isLoading ? (
            <span className="px-3 py-1.5 text-xs text-[#475569] animate-pulse">Loading…</span>
          ) : isAuthenticated ? (
            <>
              <Link href="/" className="nav-link nav-link--active" aria-current="page">
                <span className="nav-link__icon" aria-hidden="true">🏠</span>
                Dashboard
              </Link>
              <Link href="/intake" className="nav-link">
                <span className="nav-link__icon" aria-hidden="true">📥</span>
                Intake
              </Link>
              <Link href="/eval" className="nav-link">
                <span className="nav-link__icon" aria-hidden="true">📊</span>
                Eval
              </Link>
              {user?.role === "administrator" && (
                <>
                  <Link href="/admin" className="nav-link">
                    <span className="nav-link__icon" aria-hidden="true">⚙️</span>
                    Admin
                  </Link>
                </>
              )}
              <button
                onClick={handleLogout}
                className="nav-link text-[#b91c1c] hover:bg-[#fef2f2]"
              >
                <span className="nav-link__icon" aria-hidden="true">🚪</span>
                Logout
              </button>
              <span className="px-3 py-1.5 text-xs font-medium text-[#475569] capitalize">
                {user?.email}
              </span>
            </>
          ) : (
            <>
              <Link href="/login" className="nav-link">
                <span className="nav-link__icon" aria-hidden="true">🔐</span>
                Sign in
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
