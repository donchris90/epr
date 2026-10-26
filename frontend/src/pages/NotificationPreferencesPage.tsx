import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { PageHeader, Card, Button, ErrorBanner } from "../components/ui";
import { CATEGORY_LABEL, type NotificationCategory } from "../lib/notifications";

interface Pref {
  category: NotificationCategory;
  in_app: boolean;
  email: boolean;
}

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

/** Per-category in-app / email toggles, backed by
 * GET/PUT /v1/notifications/preferences. A switch can only turn
 * delivery off: it never makes the system send something it would not
 * otherwise send (email is only sent for events that request it). */
export default function NotificationPreferencesPage() {
  const [prefs, setPrefs] = useState<Pref[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    apiClient
      .get("/notifications/preferences")
      .then((res) => setPrefs(res.data.preferences))
      .catch((err) => setError(getErrorMessage(err)));
  }, []);

  function toggle(category: NotificationCategory, channel: "in_app" | "email") {
    setSaved(false);
    setPrefs((cur) => cur && cur.map((p) => (p.category === category ? { ...p, [channel]: !p[channel] } : p)));
  }

  async function save() {
    if (!prefs) return;
    setSaving(true);
    setError(null);
    try {
      const res = await apiClient.put("/notifications/preferences", { preferences: prefs });
      setPrefs(res.data.preferences);
      setSaved(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader eyebrow="Settings" title="Notifications" />
      {error && <ErrorBanner title="Something went wrong" detail={error} />}
      <Card>
        <p style={{ fontSize: 13, color: "var(--sf-navy-600)", marginBottom: 12 }}>
          Choose how you are told about each kind of event. Email is only sent for events that use it.
        </p>
        {!prefs && !error && <p style={{ fontSize: 13 }}>Loading…</p>}
        {prefs && (
          <table style={{ width: "100%", fontSize: 14, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left" }}>
                <th>Category</th>
                <th>In-app</th>
                <th>Email</th>
              </tr>
            </thead>
            <tbody>
              {prefs.map((p) => (
                <tr key={p.category}>
                  <td style={{ padding: "8px 0" }}>{CATEGORY_LABEL[p.category]}</td>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`${CATEGORY_LABEL[p.category]} in-app`}
                      checked={p.in_app}
                      onChange={() => toggle(p.category, "in_app")}
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`${CATEGORY_LABEL[p.category]} email`}
                      checked={p.email}
                      onChange={() => toggle(p.category, "email")}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {prefs && (
          <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
            <Button onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
            {saved && <span style={{ fontSize: 13 }}>Saved</span>}
          </div>
        )}
      </Card>
    </div>
  );
}
