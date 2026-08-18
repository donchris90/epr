import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/client";
import { setTokens } from "../lib/auth";
import { Button, Input, Field } from "../components/ui";

interface Preview {
  organization_name: string | null;
  invited_by_email: string | null;
  email: string;
  role_name: string | null;
}

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "This invitation is invalid or has expired.";
}

/** Public page (no auth) -- the real invite-to-account flow: shows a
 * real preview (org name, inviter, role) fetched from
 * GET /v1/org/invitations/preview, then a real password form that
 * calls POST /v1/org/invitations/accept and logs the new user
 * straight into the app, matching Phase 32's flow end to end. */
export default function AcceptInvitationPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) {
      setPreviewError("This invitation link is missing its token.");
      return;
    }
    apiClient
      .get("/org/invitations/preview", { params: { token } })
      .then((res) => setPreview(res.data))
      .catch((err) => setPreviewError(getErrorMessage(err)));
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);

    if (password.length < 8) {
      setSubmitError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setSubmitError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await apiClient.post("/org/invitations/accept", { token, password });
      setTokens(res.data.access_token, res.data.refresh_token, preview?.organization_name ?? "Workspace");
      navigate("/business-development");
    } catch (err: any) {
      setSubmitError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--sf-paper)", padding: 24 }}>
      <div style={{ width: 380, background: "#fff", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", padding: 32 }}>
        {previewError ? (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>Invitation not valid</div>
            <div style={{ fontSize: 13, color: "var(--sf-navy-600)" }}>{previewError}</div>
          </div>
        ) : !preview ? (
          <div style={{ textAlign: "center", fontSize: 13, color: "var(--sf-navy-400)" }}>Loading invitation…</div>
        ) : (
          <>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>Join {preview.organization_name ?? "SiteForge"}</div>
            <div style={{ fontSize: 13, color: "var(--sf-navy-600)", marginBottom: 20 }}>
              {preview.invited_by_email ? `Invited by ${preview.invited_by_email}` : "You've been invited"}
              {preview.role_name && ` as ${preview.role_name}`}
            </div>

            <form onSubmit={handleSubmit}>
              <Field label="Email">
                <Input value={preview.email} disabled />
              </Field>
              <Field label="Set a password">
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
              </Field>
              <Field label="Confirm password">
                <Input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={8} />
              </Field>

              {submitError && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{submitError}</div>}

              <Button type="submit" disabled={submitting} style={{ width: "100%" }}>
                {submitting ? "Joining…" : "Accept & Join"}
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
