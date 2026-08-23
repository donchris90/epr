import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../api/client";
import { useUploadDocument } from "../api/documents";
import { clearTokens } from "../lib/auth";
import { PageHeader, Card, Button, ErrorBanner, Field, Input } from "../components/ui";
import { PasswordStrengthMeter } from "../components/PasswordStrengthMeter";

interface Profile {
  id: string;
  email: string;
  status: string;
  department: string | null;
  job_title: string | null;
  avatar_url: string | null;
}

const REAL_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

/** Real "My Profile" page -- backed by GET/PUT/DELETE /v1/auth/me
 * (built earlier this session). Avatar upload reuses the existing,
 * already-tested useUploadDocument hook for the real 3-step S3/R2
 * upload flow, then links the resulting document to the profile via
 * PUT /v1/auth/me/avatar -- the backend re-validates it's a genuine
 * image from what R2 actually confirmed (never trusts the browser's
 * claimed file type), so a rejected upload here reflects a real
 * server-side check, not just a client-side guess. */
export default function ProfilePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadDocument();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);

  async function load() {
    setError(null);
    try {
      const res = await apiClient.get("/auth/me");
      setProfile(res.data);
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setPasswordError(null);

    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.");
      return;
    }

    setChangingPassword(true);
    try {
      await apiClient.put("/auth/me/password", { current_password: currentPassword, new_password: newPassword });
      setPasswordSuccess(true);
      // Real, deliberate: a successful change invalidates every
      // session for this account immediately, including this one
      // (see app/auth/jwt_utils.py's own docstring on the real
      // pwd_ts mechanism) -- the current tokens genuinely stop
      // working the moment this request succeeds, so signing out and
      // sending the person to log in again with the new password is
      // the only real, correct next step, not an arbitrary UX choice.
      setTimeout(() => {
        clearTokens();
        navigate("/login");
      }, 2000);
    } catch (err: any) {
      setPasswordError(getErrorMessage(err));
    } finally {
      setChangingPassword(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function handlePickAvatar() {
    fileInputRef.current?.click();
  }

  async function handleAvatarSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    if (!REAL_IMAGE_TYPES.includes(file.type)) {
      setError(`Please choose a real image file (JPEG, PNG, WebP, or GIF) — got "${file.type || "unknown type"}".`);
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const uploaded = await upload.mutateAsync({ file, docType: "avatar" });
      await apiClient.put("/auth/me/avatar", { document_id: uploaded.id });
      await load();
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function handleRemoveAvatar() {
    setError(null);
    try {
      await apiClient.delete("/auth/me/avatar");
      await load();
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  if (!profile) {
    return <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>;
  }

  return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader eyebrow="Settings" title="My Profile" />

      {error && <ErrorBanner title="Something went wrong" detail={error} onDismiss={() => setError(null)} />}

      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 24 }}>
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: "50%",
              overflow: "hidden",
              background: "var(--sf-paper-dim)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
              fontWeight: 700,
              color: "var(--sf-navy-400)",
              flexShrink: 0,
            }}
          >
            {profile.avatar_url ? (
              <img src={profile.avatar_url} alt="Your avatar" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            ) : (
              profile.email[0].toUpperCase()
            )}
          </div>
          <div>
            <div style={{ display: "flex", gap: 8 }}>
              <Button onClick={handlePickAvatar} disabled={uploading}>
                {uploading ? "Uploading…" : profile.avatar_url ? "Change photo" : "Upload photo"}
              </Button>
              {profile.avatar_url && (
                <Button variant="ghost" onClick={handleRemoveAvatar} disabled={uploading}>
                  Remove
                </Button>
              )}
            </div>
            <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 6 }}>JPEG, PNG, WebP, or GIF</div>
            <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp,image/gif" style={{ display: "none" }} onChange={handleAvatarSelected} />
          </div>
        </div>

        <Field label="Email">
          <Input value={profile.email} disabled />
        </Field>
        <Field label="Department">
          <Input value={profile.department ?? "—"} disabled />
        </Field>
        <Field label="Job title">
          <Input value={profile.job_title ?? "—"} disabled />
        </Field>
      </Card>

      <Card style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Change password</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 16 }}>
          Changing your password signs you out of every device, including this one.
        </p>
        {passwordSuccess ? (
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
            <PasswordStrengthMeter password={newPassword} />
            <Field label="Confirm new password">
              <Input type="password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="••••••••" />
            </Field>
            {passwordError && <ErrorBanner title="Could not change password" detail={passwordError} onDismiss={() => setPasswordError(null)} />}
            <Button type="submit" disabled={changingPassword}>
              {changingPassword ? "Changing…" : "Change password"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}
