import { useState } from "react";
import { PageHeader, Card, Field, Input, Button } from "../../components/ui";
import { useClientMe, useChangeClientPassword } from "../hooks";
import { QueryState } from "../components/QueryState";

/** Profile/account (item 16): account details plus a real,
 * working self-service password change (POST /v1/clp/auth/me/password
 * -- added alongside this page, requires the current password, unlike
 * the staff-initiated create/reset flow on the admin page). */
export default function ProfilePage() {
  const me = useClientMe();
  const changePassword = useChangeClientPassword();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    try {
      await changePassword.mutateAsync({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setSuccess(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.response?.data?.title || "Could not change your password.");
    }
  }

  return (
    <div style={{ maxWidth: 480 }}>
      <PageHeader eyebrow="Settings" title="My Account" />

      <QueryState query={me}>
        {(data: any) => (
          <Card style={{ marginBottom: 20 }}>
            <Field label="Organization">
              <Input value={data.client_organization_name} disabled />
            </Field>
            <Field label="Email">
              <Input value={data.email} disabled />
            </Field>
          </Card>
        )}
      </QueryState>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Change password</h3>
        <form onSubmit={handleSubmit}>
          <Field label="Current password">
            <Input type="password" required value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
          </Field>
          <Field label="New password">
            <Input type="password" required minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          </Field>
          {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 10 }}>{error}</div>}
          {success && <div style={{ color: "var(--sf-green)", fontSize: 12, marginBottom: 10 }}>Password updated.</div>}
          <Button type="submit" disabled={changePassword.isPending}>
            {changePassword.isPending ? "Saving…" : "Update password"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
