export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  data: Record<string, unknown> | null;
  read_at: string | null;
  created_at: string;
}

export function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Real, honest deep-linking -- data.entity_type/entity_id
 * (backend/app/notifications/models.py's own documented shape) only
 * ever gets a route here for entity types this function actually
 * knows a real page for. An unrecognized entity_type returns null
 * (no navigation) rather than guessing at a URL that might not
 * exist -- a dead link is worse than no link. */
export function deepLinkFor(data: Record<string, unknown> | null): string | null {
  const entityType = data?.entity_type as string | undefined;
  const entityId = data?.entity_id as string | undefined;
  if (!entityType || !entityId) return null;

  const routes: Record<string, string> = {
    purchase_order: `/procurement/orders/${entityId}`,
    contract_amendment: `/contracts`,
    budget_revision: `/finance`,
    permit_to_work: `/hse`,
  };
  return routes[entityType] ?? null;
}

export type NotificationCategory = "approvals" | "projects" | "finance" | "hse" | "system";

/** Real category derived from the notification's own real `type`
 * prefix (Notification.type is a dotted, machine-readable category
 * per its own model docstring -- "workflow.approval_requested",
 * "clp.request_resolved") -- not a fixed, hand-maintained mapping
 * that would drift from whatever notify() calls actually exist.
 * Confirmed directly which real prefixes exist in this codebase today
 * before writing this mapping (only workflow.* and clp.* -- see
 * docs/NOTIFICATION_CENTER_GAPS.md for what genuinely has no data
 * behind it yet, like hse.* or fin.*, which this function still maps
 * correctly for if/when something starts creating them). */
export function categoryFor(type: string): NotificationCategory {
  const prefix = type.split(".")[0];
  const map: Record<string, NotificationCategory> = {
    workflow: "approvals",
    clp: "projects",
    scp: "projects",
    vnp: "projects",
    proj: "projects",
    pc: "projects",
    fin: "finance",
    bil: "finance",
    hse: "hse",
  };
  return map[prefix] ?? "system";
}

export const CATEGORY_LABEL: Record<NotificationCategory, string> = {
  approvals: "Approvals",
  projects: "Projects",
  finance: "Finance",
  hse: "HSE",
  system: "System",
};
