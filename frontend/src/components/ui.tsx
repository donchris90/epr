import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  action,
}: {
  eyebrow?: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <div
      className="d-flex flex-column flex-md-row justify-content-md-between align-items-md-end gap-2"
      style={{
        marginBottom: 24,
        paddingBottom: 16,
        borderBottom: "1px solid var(--sf-line)",
      }}
    >
      <div>
        {eyebrow && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.02em",
              color: "var(--sf-amber)",
              marginBottom: 6,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--sf-amber)", display: "inline-block" }} />
            {eyebrow}
          </div>
        )}
        <h1 style={{ fontSize: 24 }}>{title}</h1>
      </div>
      {action}
    </div>
  );
}

export function Button({
  children,
  variant = "primary",
  ...rest
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "danger" | "ghost";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const styles: Record<string, React.CSSProperties> = {
    primary: { background: "var(--sf-navy-900)", color: "#fff", border: "1px solid var(--sf-navy-900)" },
    secondary: { background: "#fff", color: "var(--sf-navy-900)", border: "1px solid var(--sf-line)" },
    danger: { background: "var(--sf-brick)", color: "#fff", border: "1px solid var(--sf-brick)" },
    ghost: { background: "transparent", color: "var(--sf-steel)", border: "1px solid transparent" },
  };
  return (
    <button
      {...rest}
      style={{
        padding: "9px 16px",
        borderRadius: "var(--sf-radius)",
        fontSize: 13,
        fontWeight: 600,
        cursor: rest.disabled ? "not-allowed" : "pointer",
        opacity: rest.disabled ? 0.5 : 1,
        ...styles[variant],
        ...rest.style,
      }}
    >
      {children}
    </button>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid var(--sf-line)",
        borderRadius: "var(--sf-radius)",
        boxShadow: "var(--sf-shadow)",
        padding: 20,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

const badgeTones: Record<string, { bg: string; fg: string }> = {
  neutral: { bg: "var(--sf-paper-dim)", fg: "var(--sf-navy-600)" },
  amber: { bg: "var(--sf-amber-dim)", fg: "#8a5f14" },
  steel: { bg: "var(--sf-steel-dim)", fg: "var(--sf-steel)" },
  green: { bg: "var(--sf-green-dim)", fg: "var(--sf-green)" },
  brick: { bg: "var(--sf-brick-dim)", fg: "var(--sf-brick)" },
};

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: keyof typeof badgeTones }) {
  const t = badgeTones[tone];
  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        background: t.bg,
        color: t.fg,
      }}
    >
      {children}
    </span>
  );
}

export function ErrorBanner({ title, detail, onDismiss }: { title: string; detail?: string; onDismiss?: () => void }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: 12,
        padding: "12px 16px",
        marginBottom: 20,
        background: "var(--sf-brick-dim)",
        border: "1px solid var(--sf-brick)",
        borderRadius: "var(--sf-radius)",
        fontSize: 13,
      }}
    >
      <div>
        <strong style={{ color: "var(--sf-brick)" }}>{title}</strong>
        {detail && <div style={{ marginTop: 2, color: "var(--sf-navy-600)" }}>{detail}</div>}
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{ background: "none", border: "none", color: "var(--sf-brick)", cursor: "pointer", fontSize: 14, lineHeight: 1 }}
        >
          ×
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div
      style={{
        padding: "48px 24px",
        textAlign: "center",
        border: "1px dashed var(--sf-line)",
        borderRadius: "var(--sf-radius)",
        color: "var(--sf-navy-400)",
      }}
    >
      <div style={{ fontWeight: 600, color: "var(--sf-navy-600)", marginBottom: 4 }}>{title}</div>
      {hint && <div style={{ fontSize: 13 }}>{hint}</div>}
    </div>
  );
}

export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="sf-table-scroll">
      <table style={{ width: "100%", minWidth: 640, borderCollapse: "collapse", fontSize: 13 }}>
        {children}
      </table>
    </div>
  );
}

export function Th({ children }: { children?: ReactNode }) {
  return (
    <th
      style={{
        textAlign: "left",
        padding: "10px 12px",
        fontSize: 12,
        fontWeight: 700,
        color: "var(--sf-navy-600)",
        borderBottom: "2px solid var(--sf-line)",
      }}
    >
      {children}
    </th>
  );
}

export function Td({ children, mono = false, style }: { children?: ReactNode; mono?: boolean; style?: React.CSSProperties }) {
  return (
    <td
      className={mono ? "sf-mono" : undefined}
      style={{ padding: "10px 12px", borderBottom: "1px solid var(--sf-line)", ...style }}
    >
      {children}
    </td>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      style={{
        padding: "9px 12px",
        border: "1px solid var(--sf-line)",
        borderRadius: "var(--sf-radius)",
        fontSize: 13,
        fontFamily: "inherit",
        width: "100%",
        ...props.style,
      }}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      style={{
        padding: "9px 12px",
        border: "1px solid var(--sf-line)",
        borderRadius: "var(--sf-radius)",
        fontSize: 13,
        fontFamily: "inherit",
        width: "100%",
        background: "#fff",
        ...props.style,
      }}
    />
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label style={{ display: "block", marginBottom: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--sf-navy-600)", marginBottom: 4 }}>{label}</div>
      {children}
    </label>
  );
}

export function formatMoney(value: string | number | null | undefined, currency = "NGN") {
  if (value === null || value === undefined) return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-NG", { style: "currency", currency, maximumFractionDigits: 2 }).format(n);
}
