import { useState } from "react";
import { PageHeader, Card, Button, Input, Field, Badge } from "../../components/ui";
import { useRfqInvitations, submitQuote } from "../hooks";
import { getVendorPortalErrorMessage } from "../api/client";
import type { RfqInvitation } from "../types";

function QuoteForm({ rfqId, onDone }: { rfqId: string; onDone: () => void }) {
  const [price, setPrice] = useState("");
  const [lead, setLead] = useState("");
  const [terms, setTerms] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await submitQuote({
        rfq_id: rfqId,
        price,
        lead_time_days: lead ? Number(lead) : undefined,
        payment_terms: terms || undefined,
      });
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
        A quote can't be changed once submitted.
      </p>
      <Button type="submit" disabled={busy}>
        {busy ? "Submitting…" : "Submit quote"}
      </Button>
    </form>
  );
}

function stateOf(i: RfqInvitation): { label: string; tone: "green" | "amber" | "neutral" } {
  if (i.quote) return { label: "Quote submitted", tone: "green" };
  if (i.can_quote) return { label: "Open for quotes", tone: "amber" };
  return { label: "Closed", tone: "neutral" };
}

export default function RfqInvitationsPage() {
  const { items, error, loading, reload } = useRfqInvitations();
  const [openId, setOpenId] = useState<string | null>(null);

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
                </p>
              )}
              {i.can_quote &&
                (openId === i.rfq_id ? (
                  <QuoteForm
                    rfqId={i.rfq_id}
                    onDone={() => {
                      setOpenId(null);
                      reload();
                    }}
                  />
                ) : (
                  <Button style={{ marginTop: 10 }} onClick={() => setOpenId(i.rfq_id)}>
                    Submit a quote
                  </Button>
                ))}
            </Card>
          );
        })
      )}
    </div>
  );
}
