import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import {
  usePurchaseOrder,
  useIssuePurchaseOrder,
  useCreateGRN,
  useConfirmGRN,
  useCreateInvoiceMatch,
  useApproveMatchException,
  useInitiatePOApproval,
  useDecidePOApprovalStep,
} from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  pending_approval: "amber",
  approved: "steel",
  issued: "green",
  rejected: "brick",
};

const MATCH_STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  matched: "green",
  discrepancy: "brick",
  exception_approved: "amber",
};

export default function PurchaseOrderDetailPage() {
  const { poId } = useParams();
  const { data: po, isLoading } = usePurchaseOrder(poId);

  const issuePO = useIssuePurchaseOrder(poId);
  const [issueError, setIssueError] = useState<string | null>(null);
  const [waiverReason, setWaiverReason] = useState("");

  const initiateApproval = useInitiatePOApproval(poId);
  const decideStep = useDecidePOApprovalStep(poId);
  const [thresholdRole, setThresholdRole] = useState("");

  const createGRN = useCreateGRN(poId);
  const confirmGRN = useConfirmGRN(poId);
  const [receiptLines, setReceiptLines] = useState<Record<string, string>>({});

  const createMatch = useCreateInvoiceMatch(poId);
  const approveException = useApproveMatchException(poId);
  const [matchForm, setMatchForm] = useState({ vendor_invoice_reference: "", invoice_amount: "" });
  const [matchError, setMatchError] = useState<string | null>(null);
  const [exceptionReason, setExceptionReason] = useState("");

  if (isLoading || !po) return <p>Loading…</p>;

  async function handleIssue(withWaiver: boolean) {
    setIssueError(null);
    try {
      await issuePO.mutateAsync({ waiver: withWaiver, waiver_reason: withWaiver ? waiverReason : undefined });
    } catch (err) {
      // Business rule: expired vendor compliance documents block
      // issuance without an explicit, justified waiver.
      setIssueError(getErrorMessage(err));
    }
  }

  async function handleReceive(e: React.FormEvent) {
    e.preventDefault();
    const lines = Object.entries(receiptLines)
      .filter(([, qty]) => qty)
      .map(([po_line_id, quantity_received]) => ({ po_line_id, quantity_received }));
    if (!lines.length) return;
    const res: any = await createGRN.mutateAsync({ lines });
    await confirmGRN.mutateAsync(res.data.id);
    setReceiptLines({});
  }

  async function handleMatch(e: React.FormEvent) {
    e.preventDefault();
    setMatchError(null);
    try {
      await createMatch.mutateAsync(matchForm);
      setMatchForm({ vendor_invoice_reference: "", invoice_amount: "" });
    } catch (err) {
      setMatchError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Purchase Order"
        title={po.po_number}
        action={<Badge tone={STATUS_TONE[po.status] ?? "neutral"}>{po.status.replace(/_/g, " ")}</Badge>}
      />

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Line items</h3>
            {po.line_items?.length ? (
              <Table>
                <thead>
                  <tr>
                    <Th>Description</Th>
                    <Th>Qty</Th>
                    <Th>Unit price</Th>
                    <Th>Total</Th>
                    <Th>Received</Th>
                    {po.status === "issued" && <Th>Receive now</Th>}
                  </tr>
                </thead>
                <tbody>
                  {po.line_items.map((line: any) => {
                    const outstanding = Number(line.quantity) - Number(line.quantity_received || 0);
                    return (
                      <tr key={line.id}>
                        <Td>{line.description}</Td>
                        <Td mono>{line.quantity}</Td>
                        <Td mono>{line.unit_price}</Td>
                        <Td mono>{line.line_total}</Td>
                        <Td mono>{line.quantity_received || "0"}</Td>
                        {po.status === "issued" && (
                          <Td>
                            {outstanding > 0 ? (
                              <Input
                                placeholder={`up to ${outstanding}`}
                                value={receiptLines[line.id] ?? ""}
                                onChange={(e) => setReceiptLines({ ...receiptLines, [line.id]: e.target.value })}
                                style={{ width: 100 }}
                              />
                            ) : (
                              <span style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>Fully received</span>
                            )}
                          </Td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No line items.</p>
            )}
            {po.status === "issued" && (
              <div style={{ marginTop: 12 }}>
                <Button variant="secondary" onClick={handleReceive} disabled={createGRN.isPending || confirmGRN.isPending}>
                  {createGRN.isPending || confirmGRN.isPending ? "Recording…" : "Record goods receipt"}
                </Button>
              </div>
            )}
          </Card>

          {(po.status === "issued" || po.status === "approved") && (
            <Card>
              <h3 style={{ fontSize: 14, marginBottom: 4 }}>Three-way invoice match</h3>
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
                An invoice is matched against this PO's value and any confirmed goods receipt — payment is
                released only once they agree, or an exception is explicitly approved.
              </p>

              {matchError && <ErrorBanner title="Match could not be recorded" detail={matchError} />}

              <form onSubmit={handleMatch} style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 12, marginBottom: 16 }}>
                <Field label="Vendor invoice reference">
                  <Input
                    required
                    value={matchForm.vendor_invoice_reference}
                    onChange={(e) => setMatchForm({ ...matchForm, vendor_invoice_reference: e.target.value })}
                  />
                </Field>
                <Field label="Invoice amount">
                  <Input
                    required
                    value={matchForm.invoice_amount}
                    onChange={(e) => setMatchForm({ ...matchForm, invoice_amount: e.target.value })}
                  />
                </Field>
                <Button type="submit" disabled={createMatch.isPending} style={{ height: 38, alignSelf: "end" }}>
                  Match
                </Button>
              </form>

              {po.latest_match && (
                <div
                  style={{
                    padding: "10px 12px",
                    border: "1px solid var(--sf-line)",
                    borderRadius: "var(--sf-radius)",
                    fontSize: 13,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span>{po.latest_match.vendor_invoice_reference}</span>
                    <Badge tone={MATCH_STATUS_TONE[po.latest_match.match_status] ?? "neutral"}>
                      {po.latest_match.match_status.replace(/_/g, " ")}
                    </Badge>
                  </div>
                  <div className="sf-mono" style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>
                    Invoice {po.latest_match.invoice_amount} · PO {po.latest_match.po_amount} · GRN{" "}
                    {po.latest_match.grn_amount ?? "—"}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 12 }}>
                    {po.latest_match.released_for_payment ? (
                      <span style={{ color: "var(--sf-green)", fontWeight: 600 }}>Released for payment</span>
                    ) : (
                      <span style={{ color: "var(--sf-brick)", fontWeight: 600 }}>Payment blocked</span>
                    )}
                  </div>
                  {po.latest_match.match_status === "discrepancy" && (
                    <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
                      <Input
                        placeholder="Reason for approving the exception"
                        value={exceptionReason}
                        onChange={(e) => setExceptionReason(e.target.value)}
                      />
                      <Button
                        variant="secondary"
                        disabled={!exceptionReason || approveException.isPending}
                        onClick={() => approveException.mutate({ matchId: po.latest_match.id, reason: exceptionReason })}
                      >
                        Approve exception
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </Card>
          )}
        </div>

        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Details</h3>
            <div style={{ fontSize: 13, display: "grid", gap: 8 }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Total value</div>
                <div className="sf-mono">
                  {po.currency} {po.total_value}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Vendor</div>
                <div className="sf-mono" style={{ fontSize: 11 }}>
                  {po.vendor_id}
                </div>
              </div>
              {po.compliance_waiver && (
                <div>
                  <Badge tone="amber">Issued with compliance waiver</Badge>
                </div>
              )}
            </div>
          </Card>

          {po.status === "draft" && (
            <Card style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 4 }}>Start approval workflow</h3>
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
                A single-step workflow that applies to any value — add more roles for higher-value thresholds as
                needed.
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
                <Input
                  placeholder="Approver role, e.g. site_manager"
                  value={thresholdRole}
                  onChange={(e) => setThresholdRole(e.target.value)}
                />
                <Button
                  disabled={!thresholdRole || initiateApproval.isPending}
                  onClick={() => initiateApproval.mutate([{ role_required: thresholdRole, value_threshold: null }])}
                >
                  Start
                </Button>
              </div>
            </Card>
          )}

          {po.status === "pending_approval" && po.approval_steps?.length > 0 && (
            <Card style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Approval steps</h3>
              <div style={{ display: "grid", gap: 10 }}>
                {po.approval_steps.map((step: any) => (
                  <div key={step.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
                    <div>
                      <div>{step.role_required}</div>
                      <Badge tone={step.status === "approved" ? "green" : step.status === "rejected" ? "brick" : "neutral"}>
                        {step.status}
                      </Badge>
                    </div>
                    {step.status === "pending" && (
                      <div style={{ display: "flex", gap: 6 }}>
                        <Button
                          variant="secondary"
                          disabled={decideStep.isPending}
                          onClick={() => decideStep.mutate({ stepId: step.id, decision: "approved" })}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="danger"
                          disabled={decideStep.isPending}
                          onClick={() => decideStep.mutate({ stepId: step.id, decision: "rejected" })}
                        >
                          Reject
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {po.status === "approved" && (
            <Card>
              <h3 style={{ fontSize: 14, marginBottom: 4 }}>Issue to vendor</h3>
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
                Blocked if the vendor has any expired compliance document, unless issued with a recorded waiver.
              </p>

              {issueError && <ErrorBanner title="Cannot issue" detail={issueError} />}

              <Button onClick={() => handleIssue(false)} disabled={issuePO.isPending} style={{ marginBottom: issueError ? 12 : 0 }}>
                {issuePO.isPending ? "Issuing…" : "Issue PO"}
              </Button>

              {issueError && (
                <div style={{ display: "grid", gap: 8 }}>
                  <Field label="Waiver justification (required to override)">
                    <Input required value={waiverReason} onChange={(e) => setWaiverReason(e.target.value)} />
                  </Field>
                  <Button variant="danger" onClick={() => handleIssue(true)} disabled={!waiverReason || issuePO.isPending}>
                    Issue with waiver
                  </Button>
                </div>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
