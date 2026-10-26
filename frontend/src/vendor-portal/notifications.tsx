import { vendorPortalClient } from "./api/client";
import { PortalNotificationBell, PortalNotificationsPage, type PortalNotification } from "../components/PortalNotifications";

/** In-portal route for a notification, or null when it has none. */
export function notificationLink(n: PortalNotification): string | null {
  if (n.type.startsWith("vnp.banking_change")) return "/vendor/profile";
  if (n.type === "vnp.rfq_invited") return "/vendor/rfqs";
  return null;
}

const config = { client: vendorPortalClient, allPath: "/vendor/notifications", linkFor: notificationLink };

export function VendorNotificationBell() {
  return <PortalNotificationBell {...config} />;
}

export default function VendorNotificationsPage() {
  return <PortalNotificationsPage client={config.client} linkFor={config.linkFor} />;
}
