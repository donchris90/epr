import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, ErrorBanner, EmptyState } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import {
  useScopeItems,
  useAddScopeItem,
  useCreateMeasurementSheet,
  useVerifyMeasurementSheet,
  usePaymentCertificates,
  useIssuePaymentCertificate,
} from "./hooks";

export default function AgreementDetailPage() {
  const { agreementId } = useParams();
  const { data: scopeItems } = useScopeItems(agreementId);
  const addScopeItem = useAddScopeItem(agreementId);
  const [scopeForm, setScopeForm] = useState({ description: "", quantity: "", unit: "", rate: "" });

  const createSheet = useCreateMeasurementSheet();
  const [sheetForm, setSheetForm] = useState({ scope_item_id: "", verified_quantity: "" });
  const verifySheet = useVerifyMeasurementSheet();
  const [sheetIds, setSheetIds] = useState<string[]>([]);

  const { data: certificates } = usePaymentCertificates(agreementId);
  const issueCertificate = useIssuePaymentCertificate(agreementId);
  const [certNumber, setCertNumber] = useState("");
  const [certError, setCertError] = useState<string | null>(null);

  async function handleAddScope(e: React.FormEvent) {
    e.preventDefault();
    await addScopeItem.mutateAsync(scopeForm);
    setScopeForm({ description: "", quantity: "", unit: "", rate: "" });
  }

  async function handleCreateSheet(e: React.FormEvent) {
    e.preventDefault();
    const res = await createSheet.mutateAsync({ agreement_id: agreementId!, ...sheetForm });
    setSheetIds((prev) => [...prev, res.data.id]);
    setSheetForm({ scope_item_id: "", verified_quantity: "" });
  }

  async function handleIssueCertificate(e: React.FormEvent) {
    e.preventDefault();
    setCertError(null);
    try {
      await issueCertificate.mutateAsync({ certificate_number: certNumber, measurement_sheet_ids: sheetIds });
      setCertNumber("");
      setSheetIds([]);
    } catch (err) {
      setCertError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Subcontract Agreement" title="Scope, Measurement & Certification" />

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Scope items</h3>
          {scopeItems?.length ? (
            <Table>
              <thead><tr><Th>Description</Th><Th>Qty</Th><Th>Rate</Th></tr></thead>
              <tbody>
                {scopeItems.map((s: any) => (
                  <tr key={s.id}>
                    <Td>{s.description}</Td>
                    <Td mono>{s.quantity ?? "—"}</Td>
                    <Td mono>{s.rate ?? "—"}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>No scope items yet.</p>
          )}
          <form onSubmit={handleAddScope} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 8, marginTop: 12 }}>
            <Input required placeholder="Description" value={scopeForm.description} onChange={(e) => setScopeForm({ ...scopeForm, description: e.target.value })} />
            <Input placeholder="Qty" value={scopeForm.quantity} onChange={(e) => setScopeForm({ ...scopeForm, quantity: e.target.value })} />
            <Input placeholder="Rate" value={scopeForm.rate} onChange={(e) => setScopeForm({ ...scopeForm, rate: e.target.value })} />
            <Button type="submit" disabled={addScopeItem.isPending}>Add</Button>
          </form>
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>Measurement sheets</h3>
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
            A sheet must be verified before it can back a payment certificate.
          </p>
          <form onSubmit={handleCreateSheet} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr auto", gap: 8 }}>
            <select
              required
              value={sheetForm.scope_item_id}
              onChange={(e) => setSheetForm({ ...sheetForm, scope_item_id: e.target.value })}
              style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
            >
              <option value="">Scope item…</option>
              {(scopeItems ?? []).map((s: any) => (
                <option key={s.id} value={s.id}>{s.description}</option>
              ))}
            </select>
            <Input required placeholder="Verified qty" value={sheetForm.verified_quantity} onChange={(e) => setSheetForm({ ...sheetForm, verified_quantity: e.target.value })} />
            <Button type="submit" disabled={createSheet.isPending}>Create</Button>
          </form>
          {sheetIds.length > 0 && (
            <div style={{ marginTop: 12, fontSize: 12 }}>
              <div style={{ marginBottom: 6, color: "var(--sf-navy-400)" }}>Staged for this session's certificate:</div>
              {sheetIds.map((id) => (
                <div key={id} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                  <span className="sf-mono">{id.slice(0, 8)}…</span>
                  <button onClick={() => verifySheet.mutate(id)} style={{ background: "none", border: "none", color: "var(--sf-green)", fontWeight: 600, cursor: "pointer" }}>
                    Verify
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Payment certificates</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
          Issues against the verified measurement sheets staged above.
        </p>
        {certError && <ErrorBanner title="Could not issue certificate" detail={certError} onDismiss={() => setCertError(null)} />}
        <form onSubmit={handleIssueCertificate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, marginBottom: 16 }}>
          <Input required placeholder="Certificate number" value={certNumber} onChange={(e) => setCertNumber(e.target.value)} />
          <Button type="submit" disabled={issueCertificate.isPending || !sheetIds.length}>
            {issueCertificate.isPending ? "Issuing…" : "Issue certificate"}
          </Button>
        </form>
        {certificates?.length ? (
          <Table>
            <thead><tr><Th>Number</Th><Th>Gross</Th><Th>Net payable</Th><Th>Status</Th></tr></thead>
            <tbody>
              {certificates.map((c: any) => (
                <tr key={c.id}>
                  <Td mono>{c.certificate_number}</Td>
                  <Td mono>{c.gross_certified_amount}</Td>
                  <Td mono>{c.net_payable}</Td>
                  <Td>
                    <Badge tone="neutral">{c.status}</Badge>
                    {c.compliance_waiver && <Badge tone="amber">Waiver</Badge>}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <EmptyState compact title="No certificates issued yet." />
        )}
      </Card>
    </div>
  );
}
