import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { AxiosInstance } from "axios";
import { Badge, Card, EmptyState, PageHeader } from "./ui";

/** Shared notification bell + full-list page for the subcontractor and
 * vendor portals. Talks to the ordinary /v1/notifications routes
 * through the portal's own axios client (portal token), exactly like
 * the client portal's bell. `linkFor` maps a notification to an
 * in-portal route (or null for none). */
export interface PortalNotification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  data: Record<string, unknown> | null;
  read_at: string | null;
  created_at: string;
}

export interface PortalNotificationsConfig {
  client: Pick<AxiosInstance, "get" | "post">;
  allPath: string; // route of the full list page
  linkFor: (n: PortalNotification) => string | null;
}

export function timeAgo(iso: string): string {
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function PortalNotificationBell({ client, allPath, linkFor }: PortalNotificationsConfig) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<PortalNotification[] | null>(null);
  const [unread, setUnread] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  const loadCount = useCallback(async () => {
    try {
      setUnread((await client.get("/notifications/unread-count")).data.unread_count);
    } catch {
      // A missed poll just leaves a stale badge until the next one.
    }
  }, [client]);

  useEffect(() => {
    loadCount();
    const t = setInterval(loadCount, 60000);
    return () => clearInterval(t);
  }, [loadCount]);

  useEffect(() => {
    if (!open) return;
    client
      .get("/notifications", { params: { limit: 20 } })
      .then((res) => setItems(res.data.data))
      .catch(() => setItems([]));
  }, [open, client]);

  useEffect(() => {
    function outside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", outside);
    return () => document.removeEventListener("mousedown", outside);
  }, []);

  async function handleClick(n: PortalNotification) {
    if (!n.read_at) {
      try {
        await client.post(`/notifications/${n.id}/read`);
        setItems((p) => p?.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)) ?? null);
        setUnread((c) => Math.max(0, c - 1));
      } catch {
        // Non-fatal.
      }
    }
    const link = linkFor(n);
    if (link) {
      setOpen(false);
      navigate(link);
    }
  }

  async function markAll() {
    try {
      await client.post("/notifications/mark-all-read");
      setItems((p) => p?.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })) ?? null);
      setUnread(0);
    } catch {
      // Non-fatal.
    }
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        style={{ position: "relative", background: "none", border: "1px solid var(--sf-navy-700)", borderRadius: 3, width: 34, height: 34, color: "var(--sf-navy-200)", cursor: "pointer", fontSize: 15 }}
      >
        🔔
        {unread > 0 && (
          <span
            data-testid="unread-badge"
            style={{ position: "absolute", top: -4, right: -4, background: "var(--sf-brick)", color: "#fff", borderRadius: 999, fontSize: 10, fontWeight: 700, minWidth: 16, height: 16, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 3px" }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div style={{ position: "absolute", top: 40, left: 0, width: 300, maxWidth: "80vw", maxHeight: 420, overflowY: "auto", background: "#fff", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", boxShadow: "0 8px 24px rgba(11, 18, 27, 0.18)", zIndex: 50, color: "var(--sf-navy-900)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderBottom: "1px solid var(--sf-line)" }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Notifications</span>
            {unread > 0 && (
              <button onClick={markAll} style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, cursor: "pointer" }}>
                Mark all read
              </button>
            )}
          </div>
          {items === null ? (
            <div style={{ padding: 20, textAlign: "center", fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
          ) : items.length === 0 ? (
            <div style={{ padding: 20, textAlign: "center", fontSize: 13, color: "var(--sf-navy-400)" }}>No notifications yet.</div>
          ) : (
            items.map((n) => (
              <div key={n.id} onClick={() => handleClick(n)} style={{ padding: "10px 14px", borderBottom: "1px solid var(--sf-line)", cursor: "pointer", background: n.read_at ? "#fff" : "var(--sf-steel-dim)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: n.read_at ? 400 : 600 }}>{n.title}</span>
                  {!n.read_at && <Badge tone="steel">New</Badge>}
                </div>
                {n.body && <div style={{ fontSize: 12, color: "var(--sf-navy-600)", marginTop: 2 }}>{n.body}</div>}
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 4 }}>{timeAgo(n.created_at)}</div>
              </div>
            ))
          )}
          <div style={{ padding: "8px 14px", borderTop: "1px solid var(--sf-line)", textAlign: "center" }}>
            <Link to={allPath} onClick={() => setOpen(false)} style={{ fontSize: 12, color: "var(--sf-steel)" }}>
              View all notifications
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export function PortalNotificationsPage({ client, linkFor }: Omit<PortalNotificationsConfig, "allPath">) {
  const navigate = useNavigate();
  const [items, setItems] = useState<PortalNotification[] | null>(null);

  useEffect(() => {
    client
      .get("/notifications", { params: { limit: 100 } })
      .then((res) => setItems(res.data.data))
      .catch(() => setItems([]));
  }, [client]);

  async function open(n: PortalNotification) {
    if (!n.read_at) {
      try {
        await client.post(`/notifications/${n.id}/read`);
        setItems((p) => p?.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)) ?? null);
      } catch {
        // Non-fatal.
      }
    }
    const link = linkFor(n);
    if (link) navigate(link);
  }

  return (
    <div>
      <PageHeader eyebrow="Updates" title="Notifications" />
      {items === null ? (
        <p style={{ fontSize: 13 }}>Loading…</p>
      ) : items.length === 0 ? (
        <EmptyState title="No notifications yet" hint="You'll see updates here when your contractor reviews a claim, issues a certificate or decides a request." />
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {items.map((n) => (
            <div key={n.id} onClick={() => open(n)} style={{ cursor: "pointer" }}>
              <Card style={{ background: n.read_at ? "#fff" : "var(--sf-steel-dim)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: n.read_at ? 400 : 600 }}>{n.title}</div>
                  {!n.read_at && <Badge tone="steel">New</Badge>}
                </div>
                {n.body && <div style={{ fontSize: 12, color: "var(--sf-navy-600)", marginTop: 4 }}>{n.body}</div>}
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 6 }}>{new Date(n.created_at).toLocaleString()}</div>
              </Card>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
