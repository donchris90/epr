import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { EmptyState } from "./ui";
import { LoadingState } from "./Loading";
import type { LoadingVariant } from "./Loading";
import { ErrorState } from "./ErrorState";

/**
 * Renders the loading/error/empty/data branch for a react-query
 * result in one place, so every list/table/detail view handles all
 * four states the same way instead of each page re-deriving its own
 * `data === null ? ... : data.length === 0 ? ... : ...` chain (see
 * the standalone `Loading…` strings this replaces across
 * ProjectsPage, TendersPage, PurchaseOrdersPage, etc).
 *
 * (client-portal/components/QueryState.tsx is a separate, earlier
 * version of this same idea scoped to the client portal's own tabs;
 * left as-is here since its callers and e2e test already depend on
 * its exact shape, and this file is what new/refactored screens in
 * the main app should use going forward.)
 */
export function QueryState<T>({
  query,
  variant = "table",
  loadingLabel = "Loading",
  emptyTitle = "Nothing here yet",
  emptyHint,
  emptyAction,
  isEmpty,
  children,
}: {
  query: UseQueryResult<T>;
  variant?: LoadingVariant;
  loadingLabel?: string;
  emptyTitle?: string;
  emptyHint?: string;
  emptyAction?: ReactNode;
  isEmpty?: (data: T) => boolean;
  children: (data: T) => ReactNode;
}) {
  if (query.isLoading) {
    return <LoadingState variant={variant} label={loadingLabel} />;
  }

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  }

  const data = query.data as T;
  const empty = isEmpty ? isEmpty(data) : Array.isArray(data) ? data.length === 0 : data == null;
  if (empty) {
    return <EmptyState title={emptyTitle} hint={emptyHint} action={emptyAction} />;
  }

  return <>{children(data)}</>;
}
