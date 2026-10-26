import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Input, Select, Table, Td, Th } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useMyAgreements, useProgressEntries, useScopeItems, useSubmitProgress } from "./hooks";
import { useScpStore } from "./store";
import { fmtDateTime, humanize, toneFor } from "./format";

export default function ProgressPage() {
  const agreementId = useScpStore((s) => s.agreementId);
  const { data: agreements } = useMyAgreements();
  const agreement = agreements?.find((a) => a.id === agreementId);
  const { data: scope } = useScopeItems(agreementId);
  const { data: entries, isLoading, error } = useProgressEntries(agreementId);
  const submit = useSubmitProgress();

  const [scopeItemId, setScopeItemId] = useState("");
  const [qty, setQty] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  if (!agreementId) return <EmptyState title="Select an agreement" hint="Progress is submitted against one agreement at a time." />;

  const scopeLabel = (id?: string | null) => (id ? scope?.find((s) => s.id === id)?.description ?? id.slice(0, 8) : "General");
  const canSubmit = agreement?.status === "active";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSaved(false);
    const n = parseFloat(qty);
    if (!Number.isFinite(n) || n <= 0) return setFormError("Enter a quantity greater than zero.");
    try {
      await submit.mutateAsync({ agreement_id: agreementId!, scope_item_id: scopeItemId || null, submitted_quantity: String(n) });
      setQty("");
      setSaved(true);
    } catch (err) {
      setFormError(getErrorMessage(err));
    }
  }

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Submit work completed</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 14 }}>
          Quantities are reviewed and verified by the contractor before they count towards a certificate.
        </p>
        {formError && <ErrorBanner title="Couldn't submit" detail={formError} onDismiss={() => setFormError(null)} />}
        {saved && <p style={{ fontSize: 13, color: "var(--sf-green)", marginBottom: 12 }}>Progress submitted for review.</p>}
        {!canSubmit ? (
          <p style={{ fontSize: 13 }}>This agreement is <strong>{agreement?.status}</strong>; new progress can't be submitted.</p>
        ) : (
          <form onSubmit={onSubmit} style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 12, alignItems: "end" }}>
            <Field label="Scope item (optional)">
              <Select value={scopeItemId} onChange={(e) => setScopeItemId(e.target.value)}>
                <option value="">General / not itemised</option>
                {scope?.filter((s) => !s.is_lump_sum).map((s) => (
                  <option key={s.id} value={s.id}>{s.description}{s.unit ? ` (${s.unit})` : ""}</option>
                ))}
              </Select>
            </Field>
            <Field label="Quantity">
              <Input type="number" min="0" step="any" required value={qty} onChange={(e) => setQty(e.target.value)} />
            </Field>
            <Button type="submit" disabled={submit.isPending} style={{ height: 38, marginBottom: 14 }}>
              {submit.isPending ? "Submitting…" : "Submit"}
            </Button>
          </form>
        )}
      </Card>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Submission history</h3>
        {error ? (
          <ErrorBanner title="Couldn't load history" detail={getErrorMessage(error)} />
        ) : isLoading ? (
          <p>Loading…</p>
        ) : !entries?.length ? (
          <EmptyState title="Nothing submitted yet" />
        ) : (
          <Table>
            <thead><tr><Th>Submitted</Th><Th>Scope item</Th><Th>Quantity</Th><Th>Status</Th></tr></thead>
            <tbody>
              {[...entries].sort((a, b) => b.submitted_at.localeCompare(a.submitted_at)).map((p) => (
                <tr key={p.id}>
                  <Td>{fmtDateTime(p.submitted_at)}</Td>
                  <Td style={{ maxWidth: 320 }}>{scopeLabel(p.scope_item_id)}</Td>
                  <Td mono>{parseFloat(p.submitted_quantity)}</Td>
                  <Td><Badge tone={toneFor(p.status)}>{humanize(p.status)}</Badge></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
