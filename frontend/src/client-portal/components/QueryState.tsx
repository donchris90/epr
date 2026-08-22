import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { Button, EmptyState } from "../../components/ui";

function statusOf(error: any): number | undefined {
  return error?.response?.status;
}

function messageOf(error: any): string {
  return error?.response?.data?.detail || error?.response?.data?.title || "Something went wrong.";
}

/** Loading/empty/error/forbidden handling in one place -- every tab
 * in the client portal renders through this instead of repeating the
 * same four-way branch. A 403 gets its own distinct message (access
 * genuinely denied by the backend's own assert_client_project_access,
 * not a transient failure) rather than the generic retry banner,
 * since "try again" is never the right advice for it. */
export function QueryState<T>({
  query,
  emptyTitle = "Nothing here yet",
  emptyHint,
  isEmpty,
  children,
}: {
  query: UseQueryResult<T>;
  emptyTitle?: string;
  emptyHint?: string;
  isEmpty?: (data: T) => boolean;
  children: (data: T) => ReactNode;
}) {
  if (query.isLoading) {
    return (
      <div style={{ padding: 32, textAlign: "center", fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
    );
  }

  if (query.isError) {
    const status = statusOf(query.error);
    if (status === 403) {
      return (
        <div style={{ padding: 32, textAlign: "center" }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--sf-navy-900)", marginBottom: 6 }}>
            You don't have access to this
          </div>
          <div style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>
            This record isn't part of a project assigned to your account.
          </div>
        </div>
      );
    }
    return (
      <div style={{ padding: 32, textAlign: "center" }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--sf-navy-900)", marginBottom: 6 }}>
          Couldn't load this
        </div>
        <div style={{ fontSize: 13, color: "var(--sf-navy-400)", marginBottom: 12 }}>{messageOf(query.error)}</div>
        <Button variant="ghost" onClick={() => query.refetch()}>
          Try again
        </Button>
      </div>
    );
  }

  const data = query.data as T;
  const empty = isEmpty ? isEmpty(data) : Array.isArray(data) ? data.length === 0 : data == null;
  if (empty) {
    return <EmptyState title={emptyTitle} hint={emptyHint} />;
  }

  return <>{children(data)}</>;
}
