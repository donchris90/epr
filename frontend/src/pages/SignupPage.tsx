import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { apiClient } from "../api/client";
import { setTokens } from "../lib/auth";
import { Button, Input, Field } from "../components/ui";

export default function SignupPage() {
  const navigate = useNavigate();
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      // Real onboarding endpoint (app/onboarding/routes.py) -- creates
      // a brand new tenant, an Administrator role, and this user as
      // its first admin, all atomically, then auto-logs in with real
      // tokens. No pre-existing account or invite needed; this IS the
      // "create your company's account" flow.
      const res = await apiClient.post("/onboarding/signup", {
        company_name: companyName,
        admin_email: email,
        admin_password: password,
      });
      setTokens(res.data.access_token, res.data.refresh_token, companyName);
      navigate("/business-development");
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.response?.data?.title ||
          "Could not create your account. Check your details and try again."
      );
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
          <h1 style={{ color: "#fff", fontSize: 20, marginTop: 12 }}>Create your workspace</h1>
          <p style={{ color: "var(--sf-navy-400)", fontSize: 13, marginTop: 4 }}>
            Set up SiteForge for your company.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ background: "#fff", borderRadius: "var(--sf-radius)", padding: 24 }}
        >
          <Field label="Company name">
            <Input
              required
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Acme Construction Ltd"
            />
          </Field>
          <Field label="Your email">
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
            />
          </Field>
          {error && (
            <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>
          )}
          <Button type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Creating your workspace…" : "Create workspace"}
          </Button>
          <p style={{ textAlign: "center", fontSize: 12, color: "var(--sf-navy-400)", marginTop: 14 }}>
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
