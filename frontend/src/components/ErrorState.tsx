import { Button } from "./ui";
import { getErrorDetail, getErrorTitle, isRetryableError } from "../api/client";

/**
 * Full-block error state for a page/table/detail view/dashboard that
 * failed to load -- as opposed to ui.tsx's ErrorBanner, which is the
 * small dismissible strip for an error that happened *alongside*
 * otherwise-successful content (e.g. a failed action on a page that
 * still shows data). Use ErrorState when there's nothing else on
 * screen to show; use ErrorBanner when there is.
 *
 * Status-aware: 401/402 never reach here (the axios interceptor in
 * api/client.ts redirects before a component sees them). 403/404/422
 * don't show a retry button since retrying an unchanged request
 * can't fix a permission, missing-resource, or validation problem.
 */
export function ErrorState({
  error,
  onRetry,
  title,
  compact = false,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  compact?: boolean;
}) {
  const heading = title ?? getErrorTitle(error);
  const detail = getErrorDetail(error);
  const canRetry = !!onRetry && isRetryableError(error);

  return (
    <div
      role="alert"
      style={{
        padding: compact ? "20px 16px" : "48px 24px",
        textAlign: "center",
        border: "1px dashed var(--sf-line)",
        borderRadius: "var(--sf-radius)",
      }}
    >
      <div style={{ fontWeight: 700, fontSize: compact ? 14 : 15, color: "var(--sf-brick)", marginBottom: 6 }}>
        {heading}
      </div>
      {detail && (
        <div style={{ fontSize: 13, color: "var(--sf-navy-600)", marginBottom: canRetry ? 16 : 0, maxWidth: 420, marginLeft: "auto", marginRight: "auto" }}>
          {detail}
        </div>
      )}
      {canRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
