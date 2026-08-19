import { useEffect, useRef, useState } from "react";
import { apiClient } from "../api/client";
import { useUploadDocument } from "../api/documents";
import { PageHeader, Card, Button, ErrorBanner, Field, Input } from "../components/ui";

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
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadDocument();

  async function load() {
    setError(null);
    try {
      const res = await apiClient.get("/auth/me");
      setProfile(res.data);
    } catch (err: any) {
      setError(getErrorMessage(err));
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
    </div>
  );
}
