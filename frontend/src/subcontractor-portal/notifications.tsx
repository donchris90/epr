import { subcontractorPortalClient } from "./api/client";
import { PortalNotificationBell, PortalNotificationsPage, type PortalNotification } from "../components/PortalNotifications";

/** In-portal route for a notification, or null when it has none. */
export function notificationLink(n: PortalNotification): string | null {
  if (n.type.startsWith("scp.claim")) return "/subcontractor/claims";
  const agreementId = n.data?.agreement_id as string | undefined;
  if (n.type === "scp.certificate_issued" && agreementId) return `/subcontractor/agreements/${agreementId}`;
  return null;
}

const config = { client: subcontractorPortalClient, allPath: "/subcontractor/notifications", linkFor: notificationLink };

export function SubcontractorNotificationBell() {
  return <PortalNotificationBell {...config} />;
}

export default function SubcontractorNotificationsPage() {
  return <PortalNotificationsPage client={config.client} linkFor={config.linkFor} />;
}
