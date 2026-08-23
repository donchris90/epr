import { useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/client";
import { Button, Input, Field } from "../components/ui";

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong. Please try again.";
}

/** Real forgot-password page, backed by POST /v1/auth/forgot-password
 * (built earlier this session, previously genuinely missing from the
 * backend entirely). The success state is deliberately identical
 * regardless of whether the email matches a real account -- the
 * backend itself already guarantees this (see
 * app/auth/services.py:request_password_reset's own docstring), and
 * this page doesn't undermine that by, say, only showing the success
 * message after checking anything client-side. */
export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await apiClient.post("/auth/forgot-password", { email });
      // Real, deliberate: shown regardless of the backend's actual
      // internal outcome (real account vs. not), matching the
      // backend's own always-200, always-identical-message contract.
      setSubmitted(true);
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
          <h1 style={{ color: "#fff", fontSize: 20, marginTop: 12 }}>Reset your password</h1>
          <p style={{ color: "var(--sf-navy-400)", fontSize: 13, marginTop: 4 }}>
            Enter your email and we'll send you a reset link.
          </p>
        </div>

        <div style={{ background: "#fff", borderRadius: "var(--sf-radius)", padding: 24 }}>
          {submitted ? (
            <div>
              <p style={{ fontSize: 13, color: "var(--sf-navy-900)", marginBottom: 16 }}>
                If an account exists for <strong>{email}</strong>, we've sent a link to reset your password. It expires in
                1 hour.
              </p>
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>
                Didn't get it? Check your spam folder, or{" "}
                <button
                  onClick={() => setSubmitted(false)}
                  style={{ background: "none", border: "none", padding: 0, color: "var(--sf-steel)", cursor: "pointer", font: "inherit", textDecoration: "underline" }}
                >
                  try again
                </button>
                .
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <Field label="Email">
                <Input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  autoFocus
                />
              </Field>
              {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>}
              <Button type="submit" disabled={loading} style={{ width: "100%" }}>
                {loading ? "Sending…" : "Send reset link"}
              </Button>
            </form>
          )}
          <p style={{ textAlign: "center", fontSize: 12, color: "var(--sf-navy-400)", marginTop: 14 }}>
            <Link to="/login">Back to sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
