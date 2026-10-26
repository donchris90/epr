export function fmtDate(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-NG", { year: "numeric", month: "short", day: "numeric" });
}

export function fmtDateTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("en-NG", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Backend sends Decimals as strings. Display-only math; never send these back. */
export function num(value?: string | number | null): number {
  if (value === null || value === undefined || value === "") return 0;
  const n = typeof value === "number" ? value : parseFloat(value);
  return Number.isNaN(n) ? 0 : n;
}

export function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

export type Tone = "neutral" | "amber" | "steel" | "green" | "brick";

const TONES: Record<string, Tone> = {
  active: "green",
  completed: "steel",
  terminated: "brick",
  submitted: "amber",
  verified: "green",
  rejected: "brick",
  under_review: "steel",
  approved: "green",
  draft: "neutral",
  issued: "green",
};

export function toneFor(status: string): Tone {
  return TONES[status] ?? "neutral";
}
