import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, Select, ErrorBanner, EmptyState, formatMoney } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import {
  useAgreement,
  useScopeItems,
  useAddScopeItem,
  useProgressEntries,
  useSubmitProgress,
  useMeasurementSheets,
  useCreateMeasurementSheet,
  useVerifyMeasurementSheet,
  usePaymentCertificates,
  useIssuePaymentCertificate,
  useBackCharges,
  useAddBackCharge,
  useRetentionRecords,
  useAddRetention,
  useReleaseRetention,
  useClaims,
  useSubmitClaim,
  useReviewClaim,
  useComplianceDocuments,
  useAddComplianceDocument,
  usePerformanceRatings,
  useAddPerformanceRating,
  type SubcontractAgreement,
} from "./hooks";

const TABS = [
  "Overview",
  "Scope",
  "Progress",
  "Measurements",
  "Certificates",
  "Retention",
  "Back Charges",
  "Claims",
  "Compliance",
  "Performance",
] as const;
type Tab = (typeof TABS)[number];

function statusTone(status: string): "green" | "neutral" | "brick" | "amber" {
  if (status === "active" || status === "approved" || status === "verified" || status === "certified") return "green";
  if (status === "rejected" || status === "cancelled") return "brick";
  if (status === "pending" || status === "submitted" || status === "draft") return "amber";
  return "neutral";
}

/** Real subcontract agreement hub, backed entirely by real backend
 * endpoints added this batch (GET /sub/agreements/<id> plus every
 * real list endpoint each tab reads from). Follows the real workflow
 * this batch's own brief describes: Agreement -> scope -> progress ->
 * measurement -> verification -> payment certificate -> retention ->
 * finance -- each tab is a real step in that chain, not an arbitrary
 * grouping. Compliance and Performance are subcontractor-level (not
 * agreement-level) in the real data model, so those two tabs read
 * from the agreement's own real subcontractor_id. */
export default function AgreementDetailPage() {
  const { agreementId } = useParams<{ agreementId: string }>();
  const { data: agreement, isLoading, error } = useAgreement(agreementId);
  const [tab, setTab] = useState<Tab>("Overview");

  if (isLoading) return <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>;
  if (error || !agreement) return <ErrorBanner title="Could not load agreement" detail={getErrorMessage(error)} />;

  return (
    <div>
      <PageHeader
        eyebrow="Subcontract Agreement"
        title={agreement.agreement_number}
        action={<Badge tone={statusTone(agreement.status)}>{agreement.status}</Badge>}
      />
      <div style={{ display: "flex", gap: 4, marginBottom: 20, flexWrap: "wrap", borderBottom: "1px solid var(--sf-line)" }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "8px 12px",
              fontSize: 12,
              fontWeight: 600,
              background: "none",
              border: "none",
              cursor: "pointer",
              color: tab === t ? "var(--sf-navy-900)" : "var(--sf-navy-400)",
              borderBottom: tab === t ? "2px solid var(--sf-amber)" : "2px solid transparent",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && <OverviewTab agreement={agreement} />}
      {tab === "Scope" && <ScopeTab agreement={agreement} />}
      {tab === "Progress" && <ProgressTab agreement={agreement} />}
      {tab === "Measurements" && <MeasurementsTab agreement={agreement} />}
      {tab === "Certificates" && <CertificatesTab agreement={agreement} />}
      {tab === "Retention" && <RetentionTab agreement={agreement} />}
      {tab === "Back Charges" && <BackChargesTab agreement={agreement} />}
      {tab === "Claims" && <ClaimsTab agreement={agreement} />}
      {tab === "Compliance" && <ComplianceTab agreement={agreement} />}
      {tab === "Performance" && <PerformanceTab agreement={agreement} />}
    </div>
  );
}

function OverviewTab({ agreement }: { agreement: SubcontractAgreement }) {
  return (
    <Card style={{ maxWidth: 600 }}>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Agreement overview</h3>
      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: 13 }}>
        <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Value</div><span className="sf-mono">{formatMoney(agreement.value, agreement.currency)}</span></div>
        <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Retention %</div><span className="sf-mono">{agreement.retention_percentage}%</span></div>
        <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Status</div><Badge tone={statusTone(agreement.status)}>{agreement.status}</Badge></div>
        <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Currency</div>{agreement.currency}</div>
        <div style={{ gridColumn: "1 / -1" }}>
          <div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Payment terms</div>
          {agreement.payment_terms_summary || "—"}
        </div>
      </div>
    </Card>
  );
}

function ScopeTab({ agreement }: { agreement: SubcontractAgreement }) {
  const { data: items } = useScopeItems(agreement.id);
  const addItem = useAddScopeItem(agreement.id);
  const [form, setForm] = useState({ description: "", quantity: "", unit: "", rate: "" });

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    await addItem.mutateAsync(form);
    setForm({ description: "", quantity: "", unit: "", rate: "" });
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Add scope item</h3>
        <form onSubmit={handleAdd} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr auto", gap: 8 }}>
          <Input required placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <Input type="number" step="0.01" placeholder="Qty" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          <Input placeholder="Unit" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
          <Input type="number" step="0.01" placeholder="Rate" value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} />
          <Button type="submit" disabled={addItem.isPending}>Add</Button>
        </form>
      </Card>
      <Card style={{ padding: 0 }}>
        {!items?.length ? (
          <EmptyState compact title="No scope items yet." />
        ) : (
          <Table>
            <thead><tr><Th>Description</Th><Th>Qty</Th><Th>Unit</Th><Th>Rate</Th></tr></thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id}>
                  <Td>{s.description}</Td>
                  <Td mono>{s.is_lump_sum ? "Lump sum" : s.quantity ?? "—"}</Td>
                  <Td>{s.unit || "—"}</Td>
                  <Td mono>{s.rate ? formatMoney(s.rate) : s.lump_sum_amount ? formatMoney(s.lump_sum_amount) : "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function ProgressTab({ agreement }: { agreement: SubcontractAgreement }) {
  const { data: entries } = useProgressEntries(agreement.id);
  const { data: scopeItems } = useScopeItems(agreement.id);
  const submitProgress = useSubmitProgress(agreement.id);
  const [form, setForm] = useState({ scope_item_id: "", submitted_quantity: "" });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await submitProgress.mutateAsync(form);
    setForm({ scope_item_id: "", submitted_quantity: "" });
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Record progress</h3>
        <form onSubmit={handleSubmit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr auto", gap: 8 }}>
          <Select value={form.scope_item_id} onChange={(e) => setForm({ ...form, scope_item_id: e.target.value })}>
            <option value="">Scope item…</option>
            {(scopeItems ?? []).map((s) => <option key={s.id} value={s.id}>{s.description}</option>)}
          </Select>
          <Input required type="number" step="0.01" placeholder="Submitted quantity" value={form.submitted_quantity} onChange={(e) => setForm({ ...form, submitted_quantity: e.target.value })} />
          <Button type="submit" disabled={submitProgress.isPending}>Submit</Button>
        </form>
      </Card>
      <Card style={{ padding: 0 }}>
        {!entries?.length ? (
          <EmptyState compact title="No progress entries yet." />
        ) : (
          <Table>
            <thead><tr><Th>Quantity</Th><Th>Submitted</Th><Th>Status</Th></tr></thead>
            <tbody>
              {entries.map((p) => (
                <tr key={p.id}>
                  <Td mono>{p.submitted_quantity}</Td>
                  <Td mono>{p.submitted_at ? new Date(p.submitted_at).toLocaleDateString() : "—"}</Td>
                  <Td><Badge tone={statusTone(p.status)}>{p.status}</Badge></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function MeasurementsTab({ agreement }: { agreement: SubcontractAgreement }) {
  const { data: sheets } = useMeasurementSheets(agreement.id);
  const { data: scopeItems } = useScopeItems(agreement.id);
  const createSheet = useCreateMeasurementSheet(agreement.id);
  const verifySheet = useVerifyMeasurementSheet(agreement.id);
  const [form, setForm] = useState({ scope_item_id: "", verified_quantity: "" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createSheet.mutateAsync({ agreement_id: agreement.id, ...form });
    setForm({ scope_item_id: "", verified_quantity: "" });
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Create measurement sheet</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>A sheet must be verified before it can back a payment certificate.</p>
        <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr auto", gap: 8 }}>
          <Select required value={form.scope_item_id} onChange={(e) => setForm({ ...form, scope_item_id: e.target.value })}>
            <option value="">Scope item…</option>
            {(scopeItems ?? []).map((s) => <option key={s.id} value={s.id}>{s.description}</option>)}
          </Select>
          <Input required type="number" step="0.01" placeholder="Verified qty" value={form.verified_quantity} onChange={(e) => setForm({ ...form, verified_quantity: e.target.value })} />
          <Button type="submit" disabled={createSheet.isPending}>Create</Button>
        </form>
      </Card>
      <Card style={{ padding: 0 }}>
        {!sheets?.length ? (
          <EmptyState compact title="No measurement sheets yet." />
        ) : (
          <Table>
            <thead><tr><Th>Verified qty</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {sheets.map((s) => (
                <tr key={s.id}>
                  <Td mono>{s.verified_quantity}</Td>
                  <Td><Badge tone={statusTone(s.status)}>{s.status}</Badge></Td>
                  <Td style={{ textAlign: "right" }}>
                    {s.status === "draft" && (
                      <button onClick={() => verifySheet.mutate(s.id)} style={{ background: "none", border: "none", color: "var(--sf-green)", fontWeight: 600, cursor: "pointer" }}>
                        Verify
                      </button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function CertificatesTab({ agreement }: { agreement: SubcontractAgreement }) {
  const { data: sheets } = useMeasurementSheets(agreement.id);
  const { data: certificates } = usePaymentCertificates(agreement.id);
  const issueCertificate = useIssuePaymentCertificate(agreement.id);
  const [certNumber, setCertNumber] = useState("");
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const verifiedSheets = sheets?.filter((s) => s.status === "verified") ?? [];

  function toggleSheet(id: string) {
    setSelectedSheets((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function handleIssue(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await issueCertificate.mutateAsync({ certificate_number: certNumber, measurement_sheet_ids: selectedSheets });
      setCertNumber("");
      setSelectedSheets([]);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Issue payment certificate</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>Select verified measurement sheets to certify.</p>
        {verifiedSheets.length === 0 ? (
          <EmptyState compact title="No verified measurement sheets available yet." />
        ) : (
          <div style={{ marginBottom: 12, fontSize: 13 }}>
            {verifiedSheets.map((s) => (
              <label key={s.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "4px 0" }}>
                <input type="checkbox" checked={selectedSheets.includes(s.id)} onChange={() => toggleSheet(s.id)} />
                Verified qty {s.verified_quantity}
              </label>
            ))}
          </div>
        )}
        {error && <ErrorBanner title="Could not issue certificate" detail={error} onDismiss={() => setError(null)} />}
        <form onSubmit={handleIssue} style={{ display: "flex", gap: 8 }}>
          <Input required placeholder="Certificate number" value={certNumber} onChange={(e) => setCertNumber(e.target.value)} />
          <Button type="submit" disabled={issueCertificate.isPending || !selectedSheets.length}>
            {issueCertificate.isPending ? "Issuing…" : "Issue certificate"}
          </Button>
        </form>
      </Card>
      <Card style={{ padding: 0 }}>
        {!certificates?.length ? (
          <EmptyState compact title="No certificates issued yet." />
        ) : (
          <Table>
            <thead><tr><Th>Number</Th><Th>Gross</Th><Th>Net payable</Th><Th>Status</Th></tr></thead>
            <tbody>
              {certificates.map((c) => (
                <tr key={c.id}>
                  <Td mono>{c.certificate_number}</Td>
                  <Td mono>{formatMoney(c.gross_certified_amount)}</Td>
                  <Td mono>{formatMoney(c.net_payable)}</Td>
                  <Td>
                    <Badge tone={statusTone(c.status)}>{c.status}</Badge>
                    {c.compliance_waiver && <Badge tone="amber">Waiver</Badge>}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function RetentionTab({ agreement }: { agreement: SubcontractAgreement }) {
  const { data: records } = useRetentionRecords(agreement.id);
  const addRetention = useAddRetention(agreement.id);
  const releaseRetention = useReleaseRetention(agreement.id);

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Set retention</h3>
        <Button onClick={() => addRetention.mutate(agreement.retention_percentage)} disabled={addRetention.isPending}>
          Set at agreement rate ({agreement.retention_percentage}%)
        </Button>
      </Card>
      <Card style={{ padding: 0 }}>
        {!records?.length ? (
          <EmptyState compact title="No retention records yet." />
        ) : (
          <Table>
            <thead><tr><Th>%</Th><Th>Withheld</Th><Th>Substantial completion</Th><Th>Final</Th></tr></thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id}>
                  <Td mono>{r.percentage}%</Td>
                  <Td mono>{formatMoney(r.amount_withheld)}</Td>
                  <Td>
                    {r.released_substantial_completion ? (
                      <Badge tone="green">Released</Badge>
                    ) : (
                      <button onClick={() => releaseRetention.mutate({ retentionId: r.id, stage: "substantial_completion" })} style={{ background: "none", border: "none", color: "var(--sf-steel)", cursor: "pointer" }}>
                        Release
                      </button>
                    )}
                  </Td>
                  <Td>
                    {r.released_final ? (
                      <Badge tone="green">Released</Badge>
                    ) : (
                      <button onClick={() => releaseRetention.mutate({ retentionId: r.id, stage: "final" })} style={{ background: "none", border: "none", color: "var(--sf-steel)", cursor: "pointer" }}>
                        Release
                      </button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function BackChargesTab({ agreement }: { agreement: SubcontractAgreement }) {
  const { data: charges } = useBackCharges(agreement.id);
  const addCharge = useAddBackCharge(agreement.id);
  const [form, setForm] = useState({ description: "", amount: "", reason_category: "other" });

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    await addCharge.mutateAsync(form);
    setForm({ description: "", amount: "", reason_category: "other" });
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Add back charge</h3>
        <form onSubmit={handleAdd} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 8 }}>
          <Input required placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <Input required type="number" step="0.01" placeholder="Amount" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          <Select value={form.reason_category} onChange={(e) => setForm({ ...form, reason_category: e.target.value })}>
            <option value="rework">Rework</option>
            <option value="materials_supplied">Materials supplied</option>
            <option value="other">Other</option>
          </Select>
          <Button type="submit" disabled={addCharge.isPending}>Add</Button>
        </form>
      </Card>
      <Card style={{ padding: 0 }}>
        {!charges?.length ? (
          <EmptyState compact title="No back charges yet." />
        ) : (
          <Table>
            <thead><tr><Th>Description</Th><Th>Amount</Th><Th>Category</Th></tr></thead>
            <tbody>
              {charges.map((c) => (
                <tr key={c.id}>
                  <Td>{c.description}</Td>
                  <Td mono>{formatMoney(c.amount)}</Td>
                  <Td>{c.reason_category}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

const CLAIM_TYPES = ["delay", "additional_scope", "other"];

function ClaimsTab({ agreement }: { agreement: SubcontractAgreement }) {
  const { data: claims } = useClaims(agreement.id);
  const submitClaim = useSubmitClaim(agreement.id);
  const reviewClaim = useReviewClaim(agreement.id);
  const [form, setForm] = useState({ claim_type: "delay", description: "", claimed_amount: "" });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await submitClaim.mutateAsync(form);
    setForm({ claim_type: "delay", description: "", claimed_amount: "" });
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Submit claim</h3>
        <form onSubmit={handleSubmit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr 1fr auto", gap: 8 }}>
          <Select value={form.claim_type} onChange={(e) => setForm({ ...form, claim_type: e.target.value })}>
            {CLAIM_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </Select>
          <Input required placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <Input type="number" step="0.01" placeholder="Claimed amount" value={form.claimed_amount} onChange={(e) => setForm({ ...form, claimed_amount: e.target.value })} />
          <Button type="submit" disabled={submitClaim.isPending}>Submit</Button>
        </form>
      </Card>
      <Card style={{ padding: 0 }}>
        {!claims?.length ? (
          <EmptyState compact title="No claims yet." />
        ) : (
          <Table>
            <thead><tr><Th>Type</Th><Th>Description</Th><Th>Amount</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {claims.map((c) => (
                <tr key={c.id}>
                  <Td>{c.claim_type}</Td>
                  <Td>{c.description}</Td>
                  <Td mono>{c.claimed_amount ? formatMoney(c.claimed_amount) : "—"}</Td>
                  <Td><Badge tone={statusTone(c.status)}>{c.status}</Badge></Td>
                  <Td style={{ textAlign: "right" }}>
                    {c.status === "submitted" && (
                      <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                        <button onClick={() => reviewClaim.mutate({ claimId: c.id, decision: "approved" })} style={{ background: "none", border: "none", color: "var(--sf-green)", cursor: "pointer" }}>Approve</button>
                        <button onClick={() => reviewClaim.mutate({ claimId: c.id, decision: "rejected" })} style={{ background: "none", border: "none", color: "var(--sf-brick)", cursor: "pointer" }}>Reject</button>
                      </div>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

const COMPLIANCE_DOC_TYPES = ["insurance", "safety_certification", "tax_clearance", "labor_law_compliance"];

function ComplianceTab({ agreement }: { agreement: SubcontractAgreement }) {
  const { data: docs } = useComplianceDocuments(agreement.subcontractor_id);
  const addDoc = useAddComplianceDocument(agreement.subcontractor_id);
  const [form, setForm] = useState({ doc_type: "insurance", valid_until: "" });

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    await addDoc.mutateAsync(form);
    setForm({ doc_type: "insurance", valid_until: "" });
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Upload compliance record</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>Compliance is tracked per subcontractor, not per agreement.</p>
        <form onSubmit={handleAdd} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr auto", gap: 8 }}>
          <Select value={form.doc_type} onChange={(e) => setForm({ ...form, doc_type: e.target.value })}>
            {COMPLIANCE_DOC_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </Select>
          <Input type="date" value={form.valid_until} onChange={(e) => setForm({ ...form, valid_until: e.target.value })} />
          <Button type="submit" disabled={addDoc.isPending}>Add</Button>
        </form>
      </Card>
      <Card style={{ padding: 0 }}>
        {!docs?.length ? (
          <EmptyState compact title="No compliance records yet." />
        ) : (
          <Table>
            <thead><tr><Th>Type</Th><Th>Valid until</Th></tr></thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <Td>{d.doc_type.replace(/_/g, " ")}</Td>
                  <Td mono>{d.valid_until || "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function PerformanceTab({ agreement }: { agreement: SubcontractAgreement }) {
  const { data: ratings } = usePerformanceRatings(agreement.subcontractor_id);
  const addRating = useAddPerformanceRating(agreement.subcontractor_id);
  const [form, setForm] = useState({ quality_score: "", schedule_score: "", safety_score: "", responsiveness_score: "" });

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    await addRating.mutateAsync(form);
    setForm({ quality_score: "", schedule_score: "", safety_score: "", responsiveness_score: "" });
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Rate contractor</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>Performance is tracked per subcontractor, not per agreement. Scores 0–10.</p>
        <form onSubmit={handleAdd} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 8 }}>
          <Input required type="number" min="0" max="10" step="0.1" placeholder="Quality" value={form.quality_score} onChange={(e) => setForm({ ...form, quality_score: e.target.value })} />
          <Input required type="number" min="0" max="10" step="0.1" placeholder="Schedule" value={form.schedule_score} onChange={(e) => setForm({ ...form, schedule_score: e.target.value })} />
          <Input required type="number" min="0" max="10" step="0.1" placeholder="Safety" value={form.safety_score} onChange={(e) => setForm({ ...form, safety_score: e.target.value })} />
          <Input required type="number" min="0" max="10" step="0.1" placeholder="Responsiveness" value={form.responsiveness_score} onChange={(e) => setForm({ ...form, responsiveness_score: e.target.value })} />
          <Button type="submit" disabled={addRating.isPending}>Rate</Button>
        </form>
      </Card>
      <Card style={{ padding: 0 }}>
        {!ratings?.length ? (
          <EmptyState compact title="No performance ratings yet." />
        ) : (
          <Table>
            <thead><tr><Th>Quality</Th><Th>Schedule</Th><Th>Safety</Th><Th>Responsiveness</Th><Th>Overall</Th></tr></thead>
            <tbody>
              {ratings.map((r) => (
                <tr key={r.id}>
                  <Td mono>{r.quality_score}</Td>
                  <Td mono>{r.schedule_score}</Td>
                  <Td mono>{r.safety_score}</Td>
                  <Td mono>{r.responsiveness_score}</Td>
                  <Td mono><strong>{r.overall_score}</strong></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
