import { useState } from "react";
import { Button } from "../../components/ui";

/** Shared approve/reject control for a pending certificate or
 * variation order row (CLP-03 / CLP-05) -- an inline expanding notes
 * field rather than a modal, since ui.tsx has no Modal component and
 * adding one just for this would be a bigger footprint than this
 * needs. */
export function DecisionActions({
  onDecide,
  disabled,
}: {
  onDecide: (decision: "approved" | "rejected", notes: string) => Promise<void>;
  disabled?: boolean;
}) {
  const [mode, setMode] = useState<"idle" | "approve" | "reject">("idle");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(decision: "approved" | "rejected") {
    setSubmitting(true);
    setError(null);
    try {
      await onDecide(decision, notes);
      setMode("idle");
      setNotes("");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.response?.data?.title || "Could not record your decision.");
    } finally {
      setSubmitting(false);
    }
  }

  if (mode === "idle") {
    return (
      <div style={{ display: "flex", gap: 6 }}>
        <Button onClick={() => setMode("approve")} disabled={disabled}>
          Approve
        </Button>
        <Button variant="danger" onClick={() => setMode("reject")} disabled={disabled}>
          Reject
        </Button>
      </div>
    );
  }

  return (
    <div style={{ minWidth: 240 }}>
      <textarea
        autoFocus
        placeholder={mode === "approve" ? "Optional note (visible to your project team)" : "Reason for rejecting (recommended)"}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        rows={2}
        style={{
          width: "100%",
          padding: "8px 10px",
          border: "1px solid var(--sf-line)",
          borderRadius: "var(--sf-radius)",
          fontSize: 13,
          fontFamily: "inherit",
          marginBottom: 6,
          resize: "vertical",
        }}
      />
      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 6 }}>{error}</div>}
      <div style={{ display: "flex", gap: 6 }}>
        <Button
          variant={mode === "approve" ? "primary" : "danger"}
          onClick={() => submit(mode === "approve" ? "approved" : "rejected")}
          disabled={submitting}
        >
          {submitting ? "Submitting…" : mode === "approve" ? "Confirm approval" : "Confirm rejection"}
        </Button>
        <Button variant="ghost" onClick={() => setMode("idle")} disabled={submitting}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
