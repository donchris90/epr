import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader, Card, Button, Input, Field } from "../../components/ui";
import { useVendorProfile, changeVendorPassword, logoutVendor } from "../hooks";
import { getVendorPortalErrorMessage } from "../api/client";

export default function ProfilePage() {
  const navigate = useNavigate();
  const { profile, error: profileError } = useVendorProfile();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      await changeVendorPassword(currentPassword, newPassword);
      setSuccess(true);
      setTimeout(async () => {
        await logoutVendor();
        navigate("/vendor/login");
      }, 2000);
    } catch (err: any) {
      setError(getVendorPortalErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 480 }}>
      <PageHeader eyebrow="Vendor Portal" title="My Account" />

      <Card>
        <div style={{ fontSize: 13, color: "var(--sf-navy-600)" }}>
          <div style={{ marginBottom: 4 }}>
            <strong>Email:</strong> {profile?.email ?? "—"}
          </div>
          <div>
            <strong>Status:</strong> {profile?.is_active ? "Active" : "Inactive"}
          </div>
        </div>
        {profileError && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginTop: 8 }}>{profileError}</div>}
      </Card>

      <Card style={{ marginTop: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Change password</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 16 }}>
          Changing your password signs you out of your current session.
        </p>
        {success ? (
          <div style={{ fontSize: 13, color: "var(--sf-green)" }}>
            Password changed. You'll be signed out shortly — please sign in again with your new password.
          </div>
        ) : (
          <form onSubmit={handleChangePassword}>
            <Field label="Current password">
              <Input type="password" required value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} placeholder="••••••••" />
            </Field>
            <Field label="New password">
              <Input type="password" required value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="••••••••" />
            </Field>
            <Field label="Confirm new password">
              <Input type="password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="••••••••" />
            </Field>
            {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Changing…" : "Change password"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
