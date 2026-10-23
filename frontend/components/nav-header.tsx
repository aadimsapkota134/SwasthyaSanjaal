"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export function NavHeader() {
  const { user, logout, isAuthenticated, isLoading } = useAuth();
  const pathname = usePathname();

  const handleLogout = async () => {
    await logout();
  };

  const isActive = (path: string) => {
    if (path === "/" && pathname === "/") return true;
    if (path !== "/" && pathname?.startsWith(path)) return true;
    return false;
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
              <Link
                href="/"
                className={`nav-link ${isActive("/") ? "nav-link--active" : ""}`}
                aria-current={isActive("/") ? "page" : undefined}
              >
                <span className="nav-link__icon" aria-hidden="true">🏠</span>
                Dashboard
              </Link>
              <Link
                href="/intake"
                className={`nav-link ${isActive("/intake") ? "nav-link--active" : ""}`}
              >
                <span className="nav-link__icon" aria-hidden="true">📥</span>
                Intake
              </Link>
              <Link
                href="/eval"
                className={`nav-link ${isActive("/eval") ? "nav-link--active" : ""}`}
              >
                <span className="nav-link__icon" aria-hidden="true">📊</span>
                Eval
              </Link>
              {user?.role === "administrator" && (
                <Link
                  href="/admin"
                  className={`nav-link ${isActive("/admin") ? "nav-link--active" : ""}`}
                >
                  <span className="nav-link__icon" aria-hidden="true">⚙️</span>
                  Admin
                </Link>
              )}
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "4px 10px",
                  borderRadius: 16,
                  background: "#f1f5f9",
                  fontSize: "0.8rem",
                  color: "#334155",
                }}
              >
                <span style={{ fontWeight: 600 }}>{user?.full_name || user?.email}</span>
                <span className="tag tag--neutral" style={{ textTransform: "capitalize", fontSize: "0.65rem" }}>
                  {user?.role || "user"}
                </span>
              </div>
              <button
                onClick={handleLogout}
                className="nav-link text-[#b91c1c] hover:bg-[#fef2f2]"
                style={{ cursor: "pointer" }}
              >
                <span className="nav-link__icon" aria-hidden="true">🚪</span>
                Logout
              </button>
            </>
          ) : (
            <>
              <Link
                href="/"
                className={`nav-link ${isActive("/") ? "nav-link--active" : ""}`}
              >
                <span className="nav-link__icon" aria-hidden="true">🏠</span>
                Dashboard
              </Link>
              <Link
                href="/login"
                className={`nav-link ${isActive("/login") ? "nav-link--active" : ""}`}
              >
                <span className="nav-link__icon" aria-hidden="true">🔐</span>
                Sign in
              </Link>
              <Link
                href="/signup"
                className="nav-btn-primary"
              >
                <span>✨</span> Sign up
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
