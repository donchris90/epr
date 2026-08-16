import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import {
  useCertificate,
  useAddCertificateLine,
  useApplyRetention,
  useSubmitCertificate,
  useApproveCertificate,
  useRecordPayment,
} from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  submitted: "amber",
  client_approved: "green",
  rejected: "brick",
};

const TRACKING_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  submitted: "steel",
  certified: "amber",
  paid: "green",
  overdue: "brick",
};

export default function CertificateDetailPage() {
  const { certificateId } = useParams();
  const { data: cert, isLoading } = useCertificate(certificateId);

  const addLine = useAddCertificateLine(certificateId);
  const [lineForm, setLineForm] = useState({ boq_item_id: "", certified_quantity: "", rate: "", contracted_quantity: "", variation_order_id: "" });
  const [lineError, setLineError] = useState<string | null>(null);

  const applyRetention = useApplyRetention(certificateId);
  const [retentionPct, setRetentionPct] = useState("10");

  const submitCert = useSubmitCertificate(certificateId);
  const approveCert = useApproveCertificate(certificateId);
  const [approvalMethod, setApprovalMethod] = useState("in_app");

  const recordPayment = useRecordPayment(certificateId);
  const [paidAmount, setPaidAmount] = useState("");

  if (isLoading || !cert) return <p>Loading…</p>;

  const isDraft = cert.status === "draft";

  async function handleAddLine(e: React.FormEvent) {
    e.preventDefault();
    setLineError(null);
    try {
      await addLine.mutateAsync({
        boq_item_id: lineForm.boq_item_id,
        certified_quantity: lineForm.certified_quantity,
        rate: lineForm.rate,
        contracted_quantity: lineForm.contracted_quantity,
        variation_order_id: lineForm.variation_order_id || undefined,
      });
      setLineForm({ boq_item_id: "", certified_quantity: "", rate: "", contracted_quantity: "", variation_order_id: "" });
    } catch (err) {
      // Business rules: cumulative billed quantity exceeding
      // contracted (+ approved variation), or a line referencing a
      // not-yet-approved variation order, both come back as a 409
      // with the specific figures/status in `detail`.
      setLineError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Progress Certificate"
        title={cert.certificate_number}
        action={<Badge tone={STATUS_TONE[cert.status] ?? "neutral"}>{cert.status.replace(/_/g, " ")}</Badge>}
      />

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Certified lines</h3>
            {cert.lines?.length ? (
              <Table>
                <thead>
                  <tr>
                    <Th>BOQ item</Th>
                    <Th>Qty</Th>
                    <Th>Amount</Th>
                    <Th>Variation</Th>
                  </tr>
                </thead>
                <tbody>
                  {cert.lines.map((l: any) => (
                    <tr key={l.id}>
                      <Td mono style={{ fontSize: 11 }}>
                        {l.boq_item_id.slice(0, 8)}…
                      </Td>
                      <Td mono>{l.certified_quantity}</Td>
                      <Td mono>{l.amount}</Td>
                      <Td>{l.variation_order_id ? <Badge tone="amber">VO</Badge> : "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>No lines certified yet.</p>
            )}

            {isDraft && (
              <>
                {lineError && (
                  <ErrorBanner title="Cannot add this line" detail={lineError} onDismiss={() => setLineError(null)} />
                )}
                <form onSubmit={handleAddLine} style={{ marginTop: 12 }}>
                  <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
                    <Input
                      required
                      placeholder="BOQ item UUID"
                      value={lineForm.boq_item_id}
                      onChange={(e) => setLineForm({ ...lineForm, boq_item_id: e.target.value })}
                    />
                    <Input
                      required
                      placeholder="Certified qty"
                      value={lineForm.certified_quantity}
                      onChange={(e) => setLineForm({ ...lineForm, certified_quantity: e.target.value })}
                    />
                    <Input
                      required
                      placeholder="Rate"
                      value={lineForm.rate}
                      onChange={(e) => setLineForm({ ...lineForm, rate: e.target.value })}
                    />
                    <Input
                      required
                      placeholder="Contracted qty"
                      value={lineForm.contracted_quantity}
                      onChange={(e) => setLineForm({ ...lineForm, contracted_quantity: e.target.value })}
                    />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
                    <Input
                      placeholder="Variation order UUID (optional — must be approved)"
                      value={lineForm.variation_order_id}
                      onChange={(e) => setLineForm({ ...lineForm, variation_order_id: e.target.value })}
                    />
                    <Button type="submit" disabled={addLine.isPending}>
                      {addLine.isPending ? "Adding…" : "Add line"}
                    </Button>
                  </div>
                </form>
              </>
            )}
          </Card>

          {cert.payment_tracking && (
            <Card>
              <h3 style={{ fontSize: 14, marginBottom: 4 }}>Payment tracking</h3>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <Badge tone={TRACKING_TONE[cert.payment_tracking.status] ?? "neutral"}>{cert.payment_tracking.status}</Badge>
                {cert.payment_tracking.paid_amount && (
                  <span className="sf-mono" style={{ fontSize: 13 }}>
                    Paid: {cert.payment_tracking.paid_amount}
                  </span>
                )}
              </div>
              {cert.payment_tracking.status !== "paid" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
                  <Input placeholder="Amount received" value={paidAmount} onChange={(e) => setPaidAmount(e.target.value)} />
                  <Button
                    disabled={!paidAmount || recordPayment.isPending}
                    onClick={() => recordPayment.mutate({ trackingId: cert.payment_tracking.id, paid_amount: paidAmount })}
                  >
                    Record payment
                  </Button>
                </div>
              )}
            </Card>
          )}
        </div>

        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Summary</h3>
            <div style={{ fontSize: 13, display: "grid", gap: 8 }}>
              <SummaryRow label="Gross certified" value={cert.gross_certified_amount} />
              <SummaryRow label="Retention withheld" value={cert.retention_withheld} />
              <SummaryRow label="Net payable" value={cert.net_payable} strong />
            </div>
          </Card>

          {isDraft && (
            <Card style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Apply retention</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, marginBottom: 12 }}>
                <Input value={retentionPct} onChange={(e) => setRetentionPct(e.target.value)} placeholder="%" />
                <Button disabled={applyRetention.isPending} onClick={() => applyRetention.mutate(retentionPct)}>
                  Apply
                </Button>
              </div>
              <Button
                variant="secondary"
                disabled={!cert.lines?.length || submitCert.isPending}
                onClick={() => submitCert.mutate()}
              >
                {submitCert.isPending ? "Submitting…" : "Submit for approval"}
              </Button>
            </Card>
          )}

          {cert.status === "submitted" && (
            <Card>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Client approval</h3>
              <select
                value={approvalMethod}
                onChange={(e) => setApprovalMethod(e.target.value)}
                style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, width: "100%", marginBottom: 12, background: "#fff" }}
              >
                <option value="in_app">In-app approval</option>
                <option value="manual_upload">Manual upload</option>
              </select>
              <Button
                disabled={approveCert.isPending}
                onClick={() => approveCert.mutate({ approval_method: approvalMethod })}
              >
                {approveCert.isPending ? "Approving…" : "Approve as client"}
              </Button>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: "var(--sf-navy-400)" }}>{label}</span>
      <span className="sf-mono" style={{ fontWeight: strong ? 700 : 400 }}>
        {value}
      </span>
    </div>
  );
}
