import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, formatMoney, Input, Select, Table, Td, Th } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useClaims, useMyAgreements, useSubmitClaim } from "./hooks";
import { useScpStore } from "./store";
import { fmtDateTime, humanize, toneFor } from "./format";
import { CLAIM_TYPES, type ClaimType } from "./types";

const EMPTY = { claim_type: "delay" as ClaimType, description: "", claimed_amount: "", claimed_days: "" };

export default function ClaimsPage() {
  const agreementId = useScpStore((s) => s.agreementId);
  const { data: agreements } = useMyAgreements();
  const agreement = agreements?.find((a) => a.id === agreementId);
  const { data: claims, isLoading, error } = useClaims(agreementId);
  const submit = useSubmitClaim();

  const [form, setForm] = useState(EMPTY);
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  if (!agreementId) return <EmptyState title="Select an agreement" hint="Claims are raised against one agreement at a time." />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSaved(false);

    const description = form.description.trim();
    if (!description) return setFormError("Describe the basis of the claim.");

    let amount: string | null = null;
    if (form.claimed_amount.trim()) {
      const n = parseFloat(form.claimed_amount);
      if (!Number.isFinite(n) || n < 0) return setFormError("Claimed amount must be zero or more.");
      amount = String(n);
    }
    let days: number | null = null;
    if (form.claimed_days.trim()) {
      const d = Number(form.claimed_days);
      if (!Number.isInteger(d) || d < 0) return setFormError("Claimed days must be a whole number.");
      days = d;
    }
    if (amount === null && days === null) return setFormError("Enter a claimed amount, claimed days, or both.");

    try {
      await submit.mutateAsync({ agreement_id: agreementId!, claim_type: form.claim_type, description, claimed_amount: amount, claimed_days: days });
      setForm(EMPTY);
      setSaved(true);
    } catch (err) {
      setFormError(getErrorMessage(err));
    }
  }

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Submit a claim</h3>
        {formError && <ErrorBanner title="Couldn't submit" detail={formError} onDismiss={() => setFormError(null)} />}
        {saved && <p style={{ fontSize: 13, color: "var(--sf-green)", marginBottom: 12 }}>Claim submitted.</p>}
        <form onSubmit={onSubmit}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <Field label="Claim type">
              <Select value={form.claim_type} onChange={(e) => setForm({ ...form, claim_type: e.target.value as ClaimType })}>
                {CLAIM_TYPES.map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
              </Select>
            </Field>
            <Field label={`Claimed amount${agreement ? ` (${agreement.currency})` : ""}`}>
              <Input type="number" min="0" step="any" value={form.claimed_amount} onChange={(e) => setForm({ ...form, claimed_amount: e.target.value })} />
            </Field>
            <Field label="Claimed days">
              <Input type="number" min="0" step="1" value={form.claimed_days} onChange={(e) => setForm({ ...form, claimed_days: e.target.value })} />
            </Field>
          </div>
          <Field label="Description">
            <textarea
              required
              rows={4}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, fontFamily: "inherit", resize: "vertical" }}
            />
          </Field>
          <Button type="submit" disabled={submit.isPending}>{submit.isPending ? "Submitting…" : "Submit claim"}</Button>
        </form>
      </Card>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Your claims</h3>
        {error ? (
          <ErrorBanner title="Couldn't load claims" detail={getErrorMessage(error)} />
        ) : isLoading ? (
          <p>Loading…</p>
        ) : !claims?.length ? (
          <EmptyState title="No claims on this agreement" />
        ) : (
          <Table>
            <thead><tr><Th>Submitted</Th><Th>Type</Th><Th>Amount</Th><Th>Days</Th><Th>Status</Th><Th>Contractor response</Th></tr></thead>
            <tbody>
              {[...claims].sort((a, b) => b.submitted_at.localeCompare(a.submitted_at)).map((c) => (
                <tr key={c.id}>
                  <Td>{fmtDateTime(c.submitted_at)}</Td>
                  <Td style={{ textTransform: "capitalize" }}>{humanize(c.claim_type)}</Td>
                  <Td mono>{c.claimed_amount ? formatMoney(c.claimed_amount, agreement?.currency) : "—"}</Td>
                  <Td mono>{c.claimed_days ?? "—"}</Td>
                  <Td><Badge tone={toneFor(c.status)}>{humanize(c.status)}</Badge></Td>
                  <Td style={{ maxWidth: 280 }}>{c.response_notes || "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
