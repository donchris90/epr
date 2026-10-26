import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import type { AxiosInstance } from "axios";
import { Button, Input, Field } from "./ui";
import { PasswordStrengthMeter } from "./PasswordStrengthMeter";

/** Shared forgot-password / reset-password screens for the external
 * portals (subcontractor, vendor). Each portal passes its own axios
 * client, API prefix ("/scp" | "/vnp") and route base so the two
 * flows stay separate token families. The forgot screen shows the
 * same success message whether or not the email has an account,
 * matching the backend's anti-enumeration contract. */
export interface PortalResetConfig {
  client: Pick<AxiosInstance, "post">;
  apiPrefix: string;
  basePath: string; // e.g. "/subcontractor"
  portalName: string;
}

function Shell({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--sf-navy-950)" }}>
      <div style={{ width: 360 }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <span className="sf-mono" style={{ color: "var(--sf-amber)", fontSize: 14, border: "1px solid var(--sf-amber)", borderRadius: 2, padding: "2px 7px" }}>
            SF
          </span>
          <h1 style={{ color: "#fff", fontSize: 20, marginTop: 12 }}>{title}</h1>
          {subtitle && <p style={{ color: "var(--sf-navy-400)", fontSize: 13, marginTop: 4 }}>{subtitle}</p>}
        </div>
        <div style={{ background: "#fff", borderRadius: "var(--sf-radius)", padding: 24 }}>{children}</div>
      </div>
    </div>
  );
}

function errorMessage(err: any, fallback: string): string {
  return err?.response?.data?.detail || err?.response?.data?.title || fallback;
}

export function PortalForgotPassword({ client, apiPrefix, basePath, portalName }: PortalResetConfig) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await client.post(`${apiPrefix}/auth/forgot-password`, { email });
      setSubmitted(true);
    } catch (err: any) {
      setError(errorMessage(err, "Something went wrong. Please try again."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Shell title="Reset your password" subtitle={`${portalName} — enter your email and we'll send you a reset link.`}>
      {submitted ? (
        <p style={{ fontSize: 13, color: "var(--sf-navy-900)", marginBottom: 8 }}>
          If an account exists for <strong>{email}</strong>, we've sent a link to reset your password. It expires in 1 hour.
        </p>
      ) : (
        <form onSubmit={handleSubmit}>
          <Field label="Email">
            <Input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@yourcompany.com" />
          </Field>
          {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>}
          <Button type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      )}
      <p style={{ textAlign: "center", fontSize: 12, color: "var(--sf-navy-400)", marginTop: 14 }}>
        <Link to={`${basePath}/login`}>Back to sign in</Link>
      </p>
    </Shell>
  );
}

export function PortalResetPassword({ client, apiPrefix, basePath, portalName }: PortalResetConfig) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const passwordsMatch = newPassword.length > 0 && newPassword === confirmPassword;
  const canSubmit = newPassword.length >= 8 && passwordsMatch;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!canSubmit) {
      setError(newPassword.length < 8 ? "Password must be at least 8 characters." : "Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await client.post(`${apiPrefix}/auth/reset-password`, { token, new_password: newPassword });
      setSuccess(true);
      setTimeout(() => navigate(`${basePath}/login`), 2500);
    } catch (err: any) {
      setError(errorMessage(err, "This reset link is invalid or has expired."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Shell title="Set a new password" subtitle={portalName}>
      {!token ? (
        <div>
          <p style={{ fontSize: 13, color: "var(--sf-brick)", marginBottom: 12 }}>
            This link is missing its reset token. Please use the link from your email, or request a new one.
          </p>
          <Link to={`${basePath}/forgot-password`} style={{ fontSize: 12, color: "var(--sf-steel)" }}>
            Request a new reset link
          </Link>
        </div>
      ) : success ? (
        <div>
          <p style={{ fontSize: 13, color: "var(--sf-green)", marginBottom: 4 }}>Password reset successfully.</p>
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>All existing sessions have been signed out. Redirecting to sign in…</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <Field label="New password">
            <Input type="password" required autoFocus value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="••••••••" />
          </Field>
          <PasswordStrengthMeter password={newPassword} />
          <Field label="Confirm new password">
            <Input type="password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="••••••••" />
          </Field>
          {confirmPassword.length > 0 && !passwordsMatch && (
            <div style={{ fontSize: 12, color: "var(--sf-brick)", marginTop: -8, marginBottom: 14 }}>Passwords do not match.</div>
          )}
          {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>}
          <Button type="submit" disabled={loading || !canSubmit} style={{ width: "100%" }}>
            {loading ? "Resetting…" : "Reset password"}
          </Button>
        </form>
      )}
      {!success && (
        <p style={{ textAlign: "center", fontSize: 12, color: "var(--sf-navy-400)", marginTop: 14 }}>
          <Link to={`${basePath}/login`}>Back to sign in</Link>
        </p>
      )}
    </Shell>
  );
}
