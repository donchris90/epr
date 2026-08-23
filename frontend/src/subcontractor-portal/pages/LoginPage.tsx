import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, Input, Field } from "../../components/ui";
import { loginSubcontractor } from "../hooks";

/** Subcontractor portal's own sign-in screen, deliberately separate
 * from pages/LoginPage.tsx (staff) and client-portal's own login:
 * hits POST /v1/scp/auth/login, a real, distinct endpoint added for
 * this build (backend/app/modules/scp/routes.py), not the internal
 * /v1/auth/login or the client portal's /v1/clp/auth/login. */
export default function SubcontractorLoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const expired = params.get("expired") === "1";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginSubcontractor(email, password);
      navigate("/subcontractor/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.title || "Could not sign in. Check your email and password and try again.");
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
            style={{
              color: "var(--sf-amber)",
              fontSize: 14,
              border: "1px solid var(--sf-amber)",
              borderRadius: 2,
              padding: "2px 7px",
            }}
          >
            SF
          </span>
          <h1 style={{ color: "#fff", fontSize: 20, marginTop: 12 }}>Subcontractor Portal</h1>
          <p style={{ color: "var(--sf-navy-400)", fontSize: 13, marginTop: 4 }}>
            Submit progress, view certificates, and manage claims.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ background: "#fff", borderRadius: "var(--sf-radius)", padding: 24 }}>
          {expired && !error && (
            <div
              style={{
                background: "var(--sf-steel-dim)",
                color: "var(--sf-navy-700)",
                fontSize: 12,
                padding: "8px 10px",
                borderRadius: 4,
                marginBottom: 14,
              }}
            >
              Your session expired. Please sign in again.
            </div>
          )}
          <Field label="Email">
            <Input
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@yourcompany.com"
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </Field>
          {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>}
          <Button type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Signing in…" : "Sign in"}
          </Button>
          <p style={{ textAlign: "center", fontSize: 12, color: "var(--sf-navy-400)", marginTop: 14 }}>
            Don't have portal access? Contact your project manager.
          </p>
        </form>
      </div>
    </div>
  );
}
