import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../api/client";
import { PageHeader, Card, Button, Badge, EmptyState, ErrorBanner } from "../components/ui";
import { timeAgo, deepLinkFor, categoryFor, CATEGORY_LABEL, type Notification, type NotificationCategory } from "../lib/notifications";

type TabKey = "all" | "unread" | NotificationCategory;

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "unread", label: "Unread" },
  { key: "approvals", label: CATEGORY_LABEL.approvals },
  { key: "projects", label: CATEGORY_LABEL.projects },
  { key: "finance", label: CATEGORY_LABEL.finance },
  { key: "hse", label: CATEGORY_LABEL.hse },
  { key: "system", label: CATEGORY_LABEL.system },
];

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

/** Real Notification Center, backed by the real backend
 * (backend/app/notifications/routes.py) -- lists every notification
 * for the calling user (up to a real 200-row cap the backend itself
 * enforces), with real mark read/unread/all-read actions and real
 * deep links. Category tabs are derived from the notification's own
 * real `type` prefix (see lib/notifications.ts's own docstring) --
 * Approvals has real data behind it today (the workflow engine);
 * Projects has some (the client portal); Finance/HSE/System are shown
 * honestly, not hidden, but will show a real empty state until
 * something actually creates a notification with that prefix -- see
 * docs/NOTIFICATION_CENTER_GAPS.md. No notification preferences UI
 * here: confirmed directly that the backend has zero preference
 * storage of any kind, and this batch's own instruction is not to
 * build settings with no backend support. */
export default function NotificationCenterPage() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<Notification[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabKey>("all");

  async function load() {
    setError(null);
    try {
      const res = await apiClient.get("/notifications", { params: { limit: 200 } });
      setNotifications(res.data.data);
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleToggleRead(n: Notification) {
    try {
      await apiClient.post(`/notifications/${n.id}/${n.read_at ? "unread" : "read"}`);
      setNotifications((prev) => (prev ?? []).map((x) => (x.id === n.id ? { ...x, read_at: n.read_at ? null : new Date().toISOString() } : x)));
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  async function handleMarkAllRead() {
    try {
      await apiClient.post("/notifications/mark-all-read");
      setNotifications((prev) => (prev ?? []).map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })));
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  function handleOpen(n: Notification) {
    const link = deepLinkFor(n.data);
    if (link) navigate(link);
  }

  const filtered = (notifications ?? []).filter((n) => {
    if (tab === "all") return true;
    if (tab === "unread") return !n.read_at;
    return categoryFor(n.type) === tab;
  });

  const unreadCount = (notifications ?? []).filter((n) => !n.read_at).length;

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader
        eyebrow="Notifications"
        title="Notification Center"
        action={
          unreadCount > 0 ? (
            <Button variant="secondary" onClick={handleMarkAllRead}>
              Mark all read
            </Button>
          ) : undefined
        }
      />

      {error && <ErrorBanner title="Something went wrong" detail={error} onDismiss={() => setError(null)} />}

      <div role="tablist" aria-label="Notification categories" style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            style={{
              fontSize: 12,
              padding: "5px 12px",
              borderRadius: 999,
              border: "1px solid " + (tab === t.key ? "var(--sf-steel)" : "var(--sf-line)"),
              background: tab === t.key ? "var(--sf-steel-dim)" : "#fff",
              color: tab === t.key ? "var(--sf-steel)" : "var(--sf-navy-600)",
              cursor: "pointer",
            }}
          >
            {t.label}
            {t.key === "unread" && unreadCount > 0 ? ` (${unreadCount})` : ""}
          </button>
        ))}
      </div>

      <Card style={{ padding: 0 }}>
        {notifications === null ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : filtered.length === 0 ? (
          <EmptyState
            title={tab === "all" ? "No notifications yet." : "Nothing here yet."}
            hint={tab === "all" ? "You're all caught up." : "Try a different tab, or check back later."}
          />
        ) : (
          filtered.map((n) => {
            const link = deepLinkFor(n.data);
            return (
              <div
                key={n.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 12,
                  padding: "14px 16px",
                  borderBottom: "1px solid var(--sf-line)",
                  background: n.read_at ? "#fff" : "var(--sf-steel-dim)",
                }}
              >
                <div onClick={() => handleOpen(n)} style={{ flex: 1, cursor: link ? "pointer" : "default" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: n.read_at ? 400 : 600, color: "var(--sf-navy-900)" }}>{n.title}</span>
                    {!n.read_at && <Badge tone="steel">New</Badge>}
                  </div>
                  {n.body && <div style={{ fontSize: 12, color: "var(--sf-navy-600)", marginTop: 2 }}>{n.body}</div>}
                  <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 4 }}>{timeAgo(n.created_at)}</div>
                </div>
                <button
                  onClick={() => handleToggleRead(n)}
                  style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, cursor: "pointer", whiteSpace: "nowrap" }}
                >
                  {n.read_at ? "Mark unread" : "Mark read"}
                </button>
              </div>
            );
          })
        )}
      </Card>
    </div>
  );
}
