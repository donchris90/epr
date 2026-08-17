import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { platformAdminClient, getPlatformAdminErrorMessage } from "../api/platformAdminClient";
import { setPlatformAdminToken } from "../lib/platformAdminAuth";
import { Button, Input, Field } from "../components/ui";

export default function PlatformAdminLoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await platformAdminClient.post("/platform-admin/auth/login", { email, password });
      setPlatformAdminToken(res.data.access_token);
      navigate("/platform-admin/tenants");
    } catch (err: any) {
      setError(getPlatformAdminErrorMessage(err) || "Could not sign in. Check your details and try again.");
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
          <h1 style={{ color: "#fff", fontSize: 20, marginTop: 12 }}>Platform Admin</h1>
          <p style={{ color: "var(--sf-navy-400)", fontSize: 13, marginTop: 4 }}>
            Cross-tenant administration. Not a tenant workspace login.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ background: "#fff", borderRadius: "var(--sf-radius)", padding: 24 }}
        >
          <Field label="Email">
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
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
          {error && (
            <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>
          )}
          <Button type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
