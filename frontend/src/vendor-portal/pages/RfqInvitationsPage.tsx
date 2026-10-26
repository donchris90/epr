import { useState } from "react";
import { PageHeader, Card, Button, Input, Field, Badge } from "../../components/ui";
import { useRfqInvitations, submitQuote, reviseQuote, declineRfq } from "../hooks";
import { getVendorPortalErrorMessage } from "../api/client";
import type { Quotation, RfqInvitation } from "../types";

function QuoteForm({ rfqId, onDone, existing }: { rfqId: string; onDone: () => void; existing?: Quotation }) {
  const revising = !!existing;
  const [price, setPrice] = useState(existing ? String(Number(existing.price)) : "");
  const [lead, setLead] = useState(existing?.lead_time_days != null ? String(existing.lead_time_days) : "");
  const [terms, setTerms] = useState(existing?.payment_terms ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (revising) {
        await reviseQuote(rfqId, {
          price,
          lead_time_days: lead ? Number(lead) : null,
          payment_terms: terms || null,
        });
      } else {
        await submitQuote({
          rfq_id: rfqId,
          price,
          lead_time_days: lead ? Number(lead) : undefined,
          payment_terms: terms || undefined,
        });
      }
      onDone();
    } catch (err) {
      setError(getVendorPortalErrorMessage(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ marginTop: 12 }}>
      <Field label="Price">
        <Input type="number" min="0" step="0.01" required value={price} onChange={(e) => setPrice(e.target.value)} />
      </Field>
      <Field label="Lead time (days)">
        <Input type="number" min="0" value={lead} onChange={(e) => setLead(e.target.value)} />
      </Field>
      <Field label="Payment terms">
        <Input value={terms} onChange={(e) => setTerms(e.target.value)} placeholder="e.g. Net 30" />
      </Field>
      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 8 }}>{error}</div>}
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 8 }}>
        {revising
          ? "You can revise your quote until the RFQ closes. The buyer is told when you do."
          : "You can still revise your quote until the RFQ closes."}
      </p>
      <Button type="submit" disabled={busy}>
        {busy ? "Saving…" : revising ? "Save revised quote" : "Submit quote"}
      </Button>
    </form>
  );
}

function DeclineForm({ rfqId, onDone, onCancel }: { rfqId: string; onDone: () => void; onCancel: () => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await declineRfq(rfqId, reason.trim());
      onDone();
    } catch (err) {
      setError(getVendorPortalErrorMessage(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ marginTop: 12 }}>
      <Field label="Reason (optional)">
        <Input value={reason} maxLength={1000} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Out of capacity" />
      </Field>
      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 8 }}>{error}</div>}
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 8 }}>
        Declining is final: you won't be able to quote on this RFQ afterwards.
      </p>
      <div style={{ display: "flex", gap: 8 }}>
        <Button type="submit" variant="danger" disabled={busy}>{busy ? "Declining…" : "Confirm decline"}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

function stateOf(i: RfqInvitation): { label: string; tone: "green" | "amber" | "neutral" } {
  if (i.invitation_status === "declined") return { label: "Declined", tone: "neutral" };
  if (i.quote) return { label: "Quote submitted", tone: "green" };
  if (i.can_quote) return { label: "Open for quotes", tone: "amber" };
  return { label: "Closed", tone: "neutral" };
}

export default function RfqInvitationsPage() {
  const { items, error, loading, reload } = useRfqInvitations();
  const [openId, setOpenId] = useState<string | null>(null);
  const [mode, setMode] = useState<"quote" | "revise" | "decline">("quote");
  const open = (id: string, m: "quote" | "revise" | "decline") => {
    setOpenId(id);
    setMode(m);
  };
  const done = () => {
    setOpenId(null);
    reload();
  };

  return (
    <div>
      <PageHeader eyebrow="Vendor Portal" title="Requests for Quotation" />
      {error && <div style={{ color: "var(--sf-brick)", fontSize: 13, marginBottom: 16 }}>{error}</div>}

      {loading ? (
        <Card>
          <div style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        </Card>
      ) : !items || items.length === 0 ? (
        <Card>
          <div style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>You have not been invited to any RFQs yet.</div>
        </Card>
      ) : (
        items.map((i) => {
          const st = stateOf(i);
          return (
            <Card key={i.invitation_id} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ fontSize: 15, fontWeight: 600 }}>{i.title}</h3>
                <Badge tone={st.tone}>{st.label}</Badge>
              </div>
              {i.description && <p style={{ fontSize: 13, marginTop: 6 }}>{i.description}</p>}
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 6 }}>
                {i.response_deadline
                  ? `Respond by ${new Date(i.response_deadline).toLocaleString()}`
                  : "No response deadline"}
              </p>
              {i.quote && (
                <p style={{ fontSize: 13, marginTop: 8 }}>
                  Your quote: <strong>{Number(i.quote.price).toLocaleString()}</strong>
                  {i.quote.lead_time_days != null && ` · ${i.quote.lead_time_days} days`}
                  {i.quote.payment_terms && ` · ${i.quote.payment_terms}`}
                  {!!i.quote.revision_count && ` · revised ${i.quote.revision_count}×`}
                </p>
              )}
              {i.invitation_status === "declined" && (
                <p style={{ fontSize: 13, marginTop: 8 }}>
                  You declined this request{i.decline_reason ? `: ${i.decline_reason}` : "."}
                </p>
              )}
              {openId === i.rfq_id && mode === "quote" && <QuoteForm rfqId={i.rfq_id} onDone={done} />}
              {openId === i.rfq_id && mode === "revise" && i.quote && <QuoteForm rfqId={i.rfq_id} existing={i.quote} onDone={done} />}
              {openId === i.rfq_id && mode === "decline" && (
                <DeclineForm rfqId={i.rfq_id} onDone={done} onCancel={() => setOpenId(null)} />
              )}
              {openId !== i.rfq_id && (
                <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                  {i.can_quote && <Button onClick={() => open(i.rfq_id, "quote")}>Submit a quote</Button>}
                  {i.can_revise && <Button variant="secondary" onClick={() => open(i.rfq_id, "revise")}>Revise quote</Button>}
                  {i.can_decline && <Button variant="ghost" onClick={() => open(i.rfq_id, "decline")}>Decline</Button>}
                </div>
              )}
            </Card>
          );
        })
      )}
    </div>
  );
}
