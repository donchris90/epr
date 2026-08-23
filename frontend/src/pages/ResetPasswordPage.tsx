import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/client";
import { Button, Input, Field } from "../components/ui";
import { PasswordStrengthMeter } from "../components/PasswordStrengthMeter";

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "This reset link is invalid or has expired.";
}

/** Real reset-password page, backed by POST /v1/auth/reset-password
 * (built earlier this session). A successful reset genuinely
 * invalidates every previously-issued session for this account,
 * everywhere -- see app/auth/jwt_utils.py's own docstring on the real
 * pwd_ts mechanism this relies on, not just this endpoint's own
 * behavior in isolation. Redirects to login rather than auto-signing
 * the person in -- the reset link itself already proved control of
 * the account's email, but not necessarily that this is a trusted
 * device worth staying signed into. */
export default function ResetPasswordPage() {
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

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (!passwordsMatch) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await apiClient.post("/auth/reset-password", { token, new_password: newPassword });
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2500);
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--sf-navy-950)",
      }}
    >
      <div style={{ width: 360 }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <span
            className="sf-mono"
            style={{ color: "var(--sf-amber)", fontSize: 14, border: "1px solid var(--sf-amber)", borderRadius: 2, padding: "2px 7px" }}
          >
            SF
          </span>
          <h1 style={{ color: "#fff", fontSize: 20, marginTop: 12 }}>Set a new password</h1>
        </div>

        <div style={{ background: "#fff", borderRadius: "var(--sf-radius)", padding: 24 }}>
          {!token ? (
            <div>
              <p style={{ fontSize: 13, color: "var(--sf-brick)", marginBottom: 12 }}>
                This link is missing its reset token. Please use the link from your email, or request a new one.
              </p>
              <Link to="/forgot-password" style={{ fontSize: 12, color: "var(--sf-steel)" }}>
                Request a new reset link
              </Link>
            </div>
          ) : success ? (
            <div>
              <p style={{ fontSize: 13, color: "var(--sf-green)", marginBottom: 4 }}>Password reset successfully.</p>
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>
                All existing sessions have been signed out for security. Redirecting to sign in…
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <Field label="New password">
                <Input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  autoFocus
                />
              </Field>
              <PasswordStrengthMeter password={newPassword} />
              <Field label="Confirm new password">
                <Input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                />
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
              <Link to="/login">Back to sign in</Link>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
