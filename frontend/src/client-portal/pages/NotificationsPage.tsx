import { PageHeader, Card, Badge } from "../../components/ui";
import { useClientNotifications, useMarkNotificationRead } from "../hooks";
import { QueryState } from "../components/QueryState";

interface Notification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  read_at: string | null;
  created_at: string;
}

/** Notifications (item 15): the full list behind the bell dropdown --
 * same /v1/notifications data, unmodified backend, called through the
 * client's own session token. See ClientNotificationBell for the
 * dropdown version of this same data. */
export default function NotificationsPage() {
  const notifications = useClientNotifications();
  const markRead = useMarkNotificationRead();

  return (
    <div>
      <PageHeader eyebrow="Updates" title="Notifications" />
      <QueryState query={notifications} emptyTitle="No notifications yet" emptyHint="You'll see updates here when your project team responds to a request or when something needs your attention.">
        {(data: Notification[]) => (
          <div style={{ display: "grid", gap: 10 }}>
            {data.map((n) => (
              <div key={n.id} onClick={() => !n.read_at && markRead.mutate(n.id)} style={{ cursor: n.read_at ? "default" : "pointer" }}>
                <Card style={{ background: n.read_at ? "#fff" : "var(--sf-steel-dim)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                    <div style={{ fontSize: 13, fontWeight: n.read_at ? 400 : 600 }}>{n.title}</div>
                    {!n.read_at && <Badge tone="steel">New</Badge>}
                  </div>
                  {n.body && <div style={{ fontSize: 12, color: "var(--sf-navy-600)", marginTop: 4 }}>{n.body}</div>}
                  <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 6 }}>
                    {new Date(n.created_at).toLocaleString()}
                  </div>
                </Card>
              </div>
            ))}
          </div>
        )}
      </QueryState>
    </div>
  );
}
