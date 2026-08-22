/** One reusable loading component for every surface in the app.
 * Rather than a bespoke spinner/skeleton per page, every screen picks
 * a `variant` describing WHERE it's loading (not how) and gets a
 * shape-appropriate placeholder. Keeps loading UI consistent and
 * means there's exactly one place to improve it later. */

const shimmerStyle: React.CSSProperties = {
  background: "linear-gradient(90deg, var(--sf-paper-dim) 25%, var(--sf-line) 37%, var(--sf-paper-dim) 63%)",
  backgroundSize: "400% 100%",
  animation: "sf-shimmer 1.4s ease infinite",
  borderRadius: 6,
};

/** Injected once; cheap and avoids a separate CSS file for a single
 * keyframe. prefers-reduced-motion is already handled globally in
 * tokens.css (`* { animation-duration: 0.001ms !important }`), so
 * this respects that automatically. */
function ShimmerKeyframes() {
  return (
    <style>{`@keyframes sf-shimmer { 0% { background-position: 100% 0; } 100% { background-position: 0 0; } }`}</style>
  );
}

function Bar({ width = "100%", height = 14, style }: { width?: number | string; height?: number; style?: React.CSSProperties }) {
  return <div style={{ ...shimmerStyle, width, height, ...style }} />;
}

export function Spinner({ size = 16, label = "Loading" }: { size?: number; label?: string }) {
  return (
    <span
      role="status"
      aria-live="polite"
      style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
    >
      <span
        aria-hidden="true"
        style={{
          width: size,
          height: size,
          border: "2px solid var(--sf-line)",
          borderTopColor: "var(--sf-amber)",
          borderRadius: "50%",
          animation: "sf-spin 0.7s linear infinite",
          display: "inline-block",
        }}
      />
      <style>{`@keyframes sf-spin { to { transform: rotate(360deg); } }`}</style>
      <span className="sf-visually-hidden">{label}</span>
    </span>
  );
}

export type LoadingVariant = "page" | "table" | "form" | "detail" | "dashboard" | "modal" | "inline";

function TableSkeleton({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div style={{ padding: 4 }}>
      <div style={{ display: "flex", gap: 12, padding: "10px 12px", borderBottom: "2px solid var(--sf-line)" }}>
        {Array.from({ length: cols }).map((_, c) => (
          <Bar key={c} width={c === 0 ? "24%" : `${Math.max(60, 100 - c * 10)}px`} height={11} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} style={{ display: "flex", gap: 12, padding: "14px 12px", borderBottom: "1px solid var(--sf-line)" }}>
          {Array.from({ length: cols }).map((_, c) => (
            <Bar key={c} width={c === 0 ? "24%" : `${Math.max(50, 90 - c * 8)}px`} height={13} />
          ))}
        </div>
      ))}
    </div>
  );
}

function FormSkeleton({ fields = 4 }: { fields?: number }) {
  return (
    <div style={{ padding: 4 }}>
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} style={{ marginBottom: 16 }}>
          <Bar width={90} height={10} style={{ marginBottom: 6 }} />
          <Bar height={36} />
        </div>
      ))}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div style={{ padding: 4 }}>
      <Bar width={220} height={20} style={{ marginBottom: 8 }} />
      <Bar width={140} height={12} style={{ marginBottom: 24 }} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 24 }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <Bar key={i} height={64} />
        ))}
      </div>
      <Bar height={13} style={{ marginBottom: 10 }} />
      <Bar height={13} width="90%" style={{ marginBottom: 10 }} />
      <Bar height={13} width="75%" />
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div style={{ padding: 4 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 20 }} className="sf-grid-responsive">
        {Array.from({ length: 4 }).map((_, i) => (
          <Bar key={i} height={78} />
        ))}
      </div>
      <Bar height={260} />
    </div>
  );
}

function PageSkeleton() {
  return (
    <div style={{ padding: "4px 0" }}>
      <Bar width={200} height={22} style={{ marginBottom: 20 }} />
      <TableSkeleton rows={6} cols={5} />
    </div>
  );
}

/**
 * <LoadingState variant="table" /> etc. `label` is announced to
 * screen readers via role="status"; the skeleton itself is
 * aria-hidden since it's purely decorative placeholder shape.
 */
export function LoadingState({
  variant = "inline",
  label = "Loading",
  rows,
  cols,
}: {
  variant?: LoadingVariant;
  label?: string;
  rows?: number;
  cols?: number;
}) {
  const body = (() => {
    switch (variant) {
      case "page":
        return <PageSkeleton />;
      case "table":
        return <TableSkeleton rows={rows} cols={cols} />;
      case "form":
      case "modal":
        return <FormSkeleton fields={rows ?? 4} />;
      case "detail":
        return <DetailSkeleton />;
      case "dashboard":
        return <DashboardSkeleton />;
      case "inline":
      default:
        return (
          <div style={{ padding: 24, display: "flex", justifyContent: "center" }}>
            <Spinner label={label} />
          </div>
        );
    }
  })();

  return (
    <div role="status" aria-live="polite" aria-busy="true">
      <span className="sf-visually-hidden">{label}</span>
      <ShimmerKeyframes />
      <div aria-hidden="true">{body}</div>
    </div>
  );
}
