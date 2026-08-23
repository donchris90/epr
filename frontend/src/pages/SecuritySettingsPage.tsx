import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/client";
import { PageHeader, Card, Badge, ErrorBanner } from "../components/ui";

interface Profile {
  email: string;
  last_login_at: string | null;
}

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

/** Real Security Settings -- backed by GET /v1/auth/me for the parts
 * that are genuinely real (last login). MFA and an active-sessions
 * list are deliberately NOT built here: confirmed during inspection
 * that neither exists anywhere in this backend (no MFA/2FA of any
 * kind, and no session tracking beyond a single refresh-token JTI
 * blocklist -- see docs/ACCOUNT_SETTINGS_GAPS.md for the full
 * reasoning and the exact endpoints that would be needed). Shown
 * honestly as unavailable rather than a fake toggle or an empty list
 * that implies the feature works. "Sign out everywhere" IS real,
 * though not exposed as a separate button here -- changing your
 * password (linked below) already does this for every session,
 * immediately, which is this backend's actual mechanism for it. */
export default function SecuritySettingsPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get("/auth/me")
      .then((res) => setProfile(res.data))
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader eyebrow="Settings" title="Security" />

      {error && <ErrorBanner title="Something went wrong" detail={error} />}

      <Card>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Password</h3>
        <p style={{ fontSize: 13, color: "var(--sf-navy-600)", marginBottom: 12 }}>
          Changing your password signs you out of every device, everywhere, immediately.
        </p>
        <Link to="/settings/profile" style={{ fontSize: 13, color: "var(--sf-steel)" }}>
          Change password →
        </Link>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Last login</h3>
        {!profile ? (
          <div style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : profile.last_login_at ? (
          <div style={{ fontSize: 13 }}>{new Date(profile.last_login_at).toLocaleString()}</div>
        ) : (
          <div style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>No previous login on record.</div>
        )}
      </Card>

      <Card style={{ marginTop: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600 }}>Two-factor authentication</h3>
          <Badge tone="neutral">Not available</Badge>
        </div>
        <p style={{ fontSize: 13, color: "var(--sf-navy-600)" }}>
          Two-factor authentication isn't supported on this account yet.
        </p>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600 }}>Active sessions</h3>
          <Badge tone="neutral">Not available</Badge>
        </div>
        <p style={{ fontSize: 13, color: "var(--sf-navy-600)" }}>
          A list of your signed-in devices isn't available yet. Changing your password (above) will sign every device
          out immediately, which you can use today if you think your account may be compromised.
        </p>
      </Card>
    </div>
  );
}
