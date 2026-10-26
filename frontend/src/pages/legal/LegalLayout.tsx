import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { LEGAL } from "./legalConfig";

export function LegalLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", background: "var(--sf-navy-950)", padding: "32px 16px" }}>
      <div style={{ maxWidth: 760, margin: "0 auto" }}>
        <div style={{ marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="sf-mono" style={{ color: "var(--sf-amber)", fontSize: 14, border: "1px solid var(--sf-amber)", borderRadius: 2, padding: "2px 7px" }}>
            SF
          </span>
          <nav style={{ fontSize: 12, display: "flex", gap: 14 }}>
            <Link to="/privacy" style={{ color: "var(--sf-navy-200)" }}>Privacy Policy</Link>
            <Link to="/terms" style={{ color: "var(--sf-navy-200)" }}>Terms of Service</Link>
            <Link to="/login" style={{ color: "var(--sf-navy-200)" }}>Sign in</Link>
          </nav>
        </div>
        <article style={{ background: "#fff", borderRadius: "var(--sf-radius)", padding: "28px 32px", fontSize: 14, lineHeight: 1.65, color: "var(--sf-navy-900)" }}>
          <h1 style={{ fontSize: 24, marginBottom: 4 }}>{title}</h1>
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 20 }}>Last updated {LEGAL.lastUpdated}</p>
          {children}
        </article>
      </div>
    </div>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ marginBottom: 22 }}>
      <h2 style={{ fontSize: 16, marginBottom: 6 }}>{title}</h2>
      {children}
    </section>
  );
}

/** Small "Privacy · Terms" footer for sign-in and sign-up screens. */
export function LegalLinks({ color = "var(--sf-navy-400)" }: { color?: string }) {
  return (
    <p style={{ textAlign: "center", fontSize: 11, color, marginTop: 10 }}>
      <Link to="/privacy">Privacy Policy</Link> · <Link to="/terms">Terms of Service</Link>
    </p>
  );
}
