import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { clientPortalClient } from "../api/client";
import { Badge } from "../../components/ui";

interface ClientNotification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  data: Record<string, unknown> | null;
  read_at: string | null;
  created_at: string;
}

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Client-portal counterpart to components/NotificationBell.tsx --
 * kept as its own small component rather than parametrizing the
 * internal one, so the internal app's own bell (and its existing
 * test coverage) is untouched. Same backend route family
 * (/v1/notifications), just called through clientPortalClient so it
 * carries the client session token instead of the staff one -- see
 * that module's own docstring for why the route needs no change at
 * all to support this. */
export function ClientNotificationBell() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<ClientNotification[] | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  async function loadUnreadCount() {
    try {
      const res = await clientPortalClient.get("/notifications/unread-count");
      setUnreadCount(res.data.unread_count);
    } catch {
      // Silent, same reasoning as the internal bell: a missed poll
      // just means a stale badge until the next one succeeds.
    }
  }

  async function loadNotifications() {
    try {
      const res = await clientPortalClient.get("/notifications", { params: { limit: 20 } });
      setNotifications(res.data.data);
    } catch {
      setNotifications([]);
    }
  }

  useEffect(() => {
    loadUnreadCount();
    const interval = setInterval(loadUnreadCount, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (open && notifications === null) loadNotifications();
  }, [open, notifications]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleClickNotification(n: ClientNotification) {
    if (!n.read_at) {
      try {
        await clientPortalClient.post(`/notifications/${n.id}/read`);
        setNotifications((prev) => prev?.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)) ?? null);
        setUnreadCount((c) => Math.max(0, c - 1));
      } catch {
        // Non-fatal, same as internal bell.
      }
    }
    // Deliberately narrower than the internal bell's deep-linking:
    // the only client-relevant notification type wired so far is
    // clp_request_resolved (see backend/app/modules/clp/services.py:
    // resolve_client_request) -- data.project_id is what that one
    // carries.
    const projectId = n.data?.project_id as string | undefined;
    if (projectId) {
      setOpen(false);
      navigate(`/portal/projects/${projectId}/issues`);
    }
  }

  async function handleMarkAllRead() {
    try {
      await clientPortalClient.post("/notifications/mark-all-read");
      setNotifications((prev) => prev?.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })) ?? null);
      setUnreadCount(0);
    } catch {
      // Non-fatal.
    }
  }

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        style={{
          position: "relative",
          background: "none",
          border: "1px solid var(--sf-navy-700)",
          borderRadius: 3,
          width: 34,
          height: 34,
          color: "var(--sf-navy-200)",
          cursor: "pointer",
          fontSize: 15,
        }}
      >
        🔔
        {unreadCount > 0 && (
          <span
            style={{
              position: "absolute",
              top: -4,
              right: -4,
              background: "var(--sf-brick)",
              color: "#fff",
              borderRadius: 999,
              fontSize: 10,
              fontWeight: 700,
              minWidth: 16,
              height: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 3px",
            }}
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: 40,
            right: 0,
            width: 340,
            maxHeight: 420,
            overflowY: "auto",
            background: "#fff",
            border: "1px solid var(--sf-line)",
            borderRadius: "var(--sf-radius)",
            boxShadow: "0 8px 24px rgba(11, 18, 27, 0.18)",
            zIndex: 50,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderBottom: "1px solid var(--sf-line)" }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--sf-navy-900)" }}>Notifications</span>
            {unreadCount > 0 && (
              <button onClick={handleMarkAllRead} style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, cursor: "pointer" }}>
                Mark all read
              </button>
            )}
          </div>

          {notifications === null ? (
            <div style={{ padding: 20, textAlign: "center", fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
          ) : notifications.length === 0 ? (
            <div style={{ padding: 20, textAlign: "center", fontSize: 13, color: "var(--sf-navy-400)" }}>No notifications yet.</div>
          ) : (
            notifications.map((n) => (
              <div
                key={n.id}
                onClick={() => handleClickNotification(n)}
                style={{
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--sf-line)",
                  cursor: "pointer",
                  background: n.read_at ? "#fff" : "var(--sf-steel-dim)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: n.read_at ? 400 : 600, color: "var(--sf-navy-900)" }}>{n.title}</span>
                  {!n.read_at && <Badge tone="steel">New</Badge>}
                </div>
                {n.body && <div style={{ fontSize: 12, color: "var(--sf-navy-600)", marginTop: 2 }}>{n.body}</div>}
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 4 }}>{timeAgo(n.created_at)}</div>
              </div>
            ))
          )}
          <div style={{ padding: "8px 14px", borderTop: "1px solid var(--sf-line)", textAlign: "center" }}>
            <Link to="/portal/notifications" onClick={() => setOpen(false)} style={{ fontSize: 12, color: "var(--sf-steel)" }}>
              View all notifications
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
