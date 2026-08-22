import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, Field, Select, EmptyState } from "../../components/ui";
import { LoadingState } from "../../components/Loading";
import { ErrorState } from "../../components/ErrorState";
import {
  useTender,
  useBOQItems,
  useAddBOQItem,
  useAddChecklistItem,
  useSubmissionReadiness,
  useSubmitTender,
  useBidDocuments,
  useAddBidDocument,
  useApprovalSteps,
  useInitiateApprovalWorkflow,
  useDecideApprovalStep,
  useReopenForRevision,
  useCreateRFI,
  useRespondToRFI,
  useCreateClarification,
  useAcknowledgeClarification,
  useJVPartners,
  useAddJVPartner,
  useRecordTenderOutcome,
} from "./hooks";
import { useOpportunity } from "../bdc/hooks";
import { useToast } from "../../lib/toast";
import { getErrorMessage } from "../../api/client";
import type { RFI, Clarification } from "./types";
import { TENDER_STATUS_LABELS } from "./types";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  in_estimate: "amber",
  in_approval: "amber",
  submitted: "steel",
  awarded: "green",
  lost: "brick",
};

export default function TenderDetailPage() {
  const { tenderId } = useParams();
  const tenderQuery = useTender(tenderId);
  const tender = tenderQuery.data;
  const opportunity = useOpportunity(tender?.opportunity_id);
  const { data: boqItems } = useBOQItems(tenderId);
  const addBOQItem = useAddBOQItem(tenderId);
  const addChecklistItem = useAddChecklistItem(tenderId);
  const { data: readiness, refetch: refetchReadiness } = useSubmissionReadiness(tenderId);
  const submitTender = useSubmitTender(tenderId);
  const { data: bidDocuments } = useBidDocuments(tenderId);
  const addBidDocument = useAddBidDocument(tenderId);
  const { data: approvalSteps } = useApprovalSteps(tenderId);
  const initiateApproval = useInitiateApprovalWorkflow(tenderId);
  const decideStep = useDecideApprovalStep(tenderId);
  const reopen = useReopenForRevision(tenderId);
  const createRFI = useCreateRFI(tenderId);
  const respondRFI = useRespondToRFI();
  const createClarification = useCreateClarification(tenderId);
  const acknowledgeClarification = useAcknowledgeClarification();
  const { data: jvPartners } = useJVPartners(tenderId);
  const addJVPartner = useAddJVPartner(tenderId);
  const recordOutcome = useRecordTenderOutcome(tenderId);
  const toast = useToast();

  const [itemDescription, setItemDescription] = useState("");
  const [itemUnit, setItemUnit] = useState("");
  const [itemQty, setItemQty] = useState("");
  const [checklistLabel, setChecklistLabel] = useState("");
  const [docType, setDocType] = useState("");
  const [approvalRoles, setApprovalRoles] = useState("");
  const [reopenReason, setReopenReason] = useState<string | null>(null);
  const [rfiQuestion, setRfiQuestion] = useState("");
  const [sessionRFIs, setSessionRFIs] = useState<RFI[]>([]);
  const [rfiResponses, setRfiResponses] = useState<Record<string, string>>({});
  const [clarificationNumber, setClarificationNumber] = useState("");
  const [clarificationDesc, setClarificationDesc] = useState("");
  const [sessionClarifications, setSessionClarifications] = useState<Clarification[]>([]);
  const [jvName, setJvName] = useState("");
  const [jvScope, setJvScope] = useState("");
  const [jvFinancial, setJvFinancial] = useState("");
  const [outcomeOpen, setOutcomeOpen] = useState(false);
  const [outcome, setOutcome] = useState<"won" | "lost">("won");
  const [winningPrice, setWinningPrice] = useState("");

  async function handleAddBOQItem(e: React.FormEvent) {
    e.preventDefault();
    await addBOQItem.mutateAsync({ description: itemDescription, unit: itemUnit || undefined, quantity: itemQty || undefined });
    setItemDescription("");
    setItemUnit("");
    setItemQty("");
  }

  async function handleAddChecklistItem(e: React.FormEvent) {
    e.preventDefault();
    await addChecklistItem.mutateAsync({ label: checklistLabel });
    setChecklistLabel("");
    refetchReadiness();
  }

  async function handleSubmit() {
    try {
      await submitTender.mutateAsync({ method: "portal", submitted_at: new Date().toISOString() });
      toast.success("Tender submitted.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleAddBidDocument(e: React.FormEvent) {
    e.preventDefault();
    try {
      await addBidDocument.mutateAsync({ doc_type: docType });
      setDocType("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleInitiateApproval(e: React.FormEvent) {
    e.preventDefault();
    const roles = approvalRoles
      .split(",")
      .map((r) => r.trim())
      .filter(Boolean)
      .map((role_required) => ({ role_required }));
    if (roles.length === 0) return;
    try {
      await initiateApproval.mutateAsync(roles);
      toast.success("Approval workflow initiated. The estimate is now locked.");
      setApprovalRoles("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleDecideStep(stepId: string, decision: "approved" | "rejected") {
    try {
      await decideStep.mutateAsync({ stepId, decision });
      toast.success(decision === "approved" ? "Step approved." : "Step rejected.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleReopen() {
    if (!reopenReason?.trim()) return;
    try {
      await reopen.mutateAsync(reopenReason.trim());
      toast.success("Tender reopened for revision.");
      setReopenReason(null);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleCreateRFI(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await createRFI.mutateAsync({ question: rfiQuestion });
      setSessionRFIs((prev) => [...prev, res.data]);
      setRfiQuestion("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleRespondRFI(rfiId: string) {
    const response = rfiResponses[rfiId];
    if (!response?.trim()) return;
    try {
      const res = await respondRFI.mutateAsync({ rfiId, response: response.trim() });
      setSessionRFIs((prev) => prev.map((r) => (r.id === rfiId ? res.data : r)));
      toast.success("RFI response recorded.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleCreateClarification(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await createClarification.mutateAsync({ addendum_number: clarificationNumber, description: clarificationDesc });
      setSessionClarifications((prev) => [...prev, res.data]);
      setClarificationNumber("");
      setClarificationDesc("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleAcknowledgeClarification(id: string) {
    try {
      const res = await acknowledgeClarification.mutateAsync(id);
      setSessionClarifications((prev) => prev.map((c) => (c.id === id ? res.data : c)));
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleAddJVPartner(e: React.FormEvent) {
    e.preventDefault();
    try {
      await addJVPartner.mutateAsync({ partner_name: jvName, scope_share_pct: jvScope, financial_share_pct: jvFinancial });
      setJvName("");
      setJvScope("");
      setJvFinancial("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleRecordOutcome() {
    try {
      await recordOutcome.mutateAsync({ outcome, winning_price: outcome === "won" ? winningPrice || undefined : undefined });
      toast.success(`Recorded as ${outcome === "won" ? "Awarded" : "Lost"}.`);
      setOutcomeOpen(false);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  if (tenderQuery.isLoading) {
    return (
      <div>
        <PageHeader eyebrow="Tender-to-Contract" title="Tender" />
        <LoadingState variant="detail" label="Loading tender" />
      </div>
    );
  }

  if (tenderQuery.isError) {
    return (
      <div>
        <PageHeader eyebrow="Tender-to-Contract" title="Tender" />
        <ErrorState error={tenderQuery.error} onRetry={() => tenderQuery.refetch()} />
      </div>
    );
  }

  if (!tender) {
    return (
      <div>
        <PageHeader eyebrow="Tender-to-Contract" title="Tender not found" />
        <EmptyState title="Tender not found" hint="It may have been removed, or the link is out of date." />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Tender-to-Contract"
        title={tender.reference_number}
        action={<Badge tone={STATUS_TONE[tender.status] ?? "neutral"}>{TENDER_STATUS_LABELS[tender.status]}</Badge>}
      />

      <Card style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 2 }}>Related opportunity</div>
            {opportunity.data ? (
              <Link to={`/business-development/opportunities/${opportunity.data.id}`} style={{ fontWeight: 600, fontSize: 13 }}>
                {opportunity.data.name}
              </Link>
            ) : opportunity.isLoading ? (
              <span style={{ fontSize: 13 }}>…</span>
            ) : (
              <span style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>—</span>
            )}
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 2 }}>Submission deadline</div>
            <span className="sf-mono" style={{ fontSize: 13 }}>
              {tender.submission_deadline ? new Date(tender.submission_deadline).toLocaleDateString() : "—"}
            </span>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 2 }}>Estimate</div>
            <span style={{ fontSize: 13 }}>{tender.estimate_locked ? "Locked (in approval)" : "Editable"}</span>
          </div>
          {tender.reopen_count > 0 && (
            <div>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 2 }}>Reopened</div>
              <span style={{ fontSize: 13 }}>{tender.reopen_count} time(s)</span>
            </div>
          )}
        </div>
      </Card>

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>BOQ items</h3>
            <form onSubmit={handleAddBOQItem} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "3fr 1fr 1fr auto", gap: 8, marginBottom: 16 }}>
              <Input required placeholder="Description" value={itemDescription} onChange={(e) => setItemDescription(e.target.value)} disabled={tender.estimate_locked} />
              <Input placeholder="Unit" value={itemUnit} onChange={(e) => setItemUnit(e.target.value)} disabled={tender.estimate_locked} />
              <Input placeholder="Qty" value={itemQty} onChange={(e) => setItemQty(e.target.value)} disabled={tender.estimate_locked} />
              <Button type="submit" variant="secondary" disabled={addBOQItem.isPending || tender.estimate_locked}>
                Add
              </Button>
            </form>
            {tender.estimate_locked && (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
                The estimate is locked while this tender is in approval — reopen it for revision to make changes.
              </p>
            )}

            {boqItems?.length ? (
              <Table ariaLabel="BOQ items">
                <thead>
                  <tr>
                    <Th>Description</Th>
                    <Th>Unit</Th>
                    <Th>Qty</Th>
                  </tr>
                </thead>
                <tbody>
                  {boqItems.map((item) => (
                    <tr key={item.id}>
                      <Td>{item.description}</Td>
                      <Td mono>{item.unit || "—"}</Td>
                      <Td mono>{item.quantity || "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No BOQ items imported yet.</p>
            )}
          </Card>

          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Bid documents</h3>
            <form onSubmit={handleAddBidDocument} style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              <Input required placeholder="Document type (e.g. bid_bond, technical_proposal)" value={docType} onChange={(e) => setDocType(e.target.value)} style={{ flex: 1 }} />
              <Button type="submit" variant="secondary" disabled={addBidDocument.isPending}>
                Add
              </Button>
            </form>
            {bidDocuments?.length ? (
              <Table ariaLabel="Bid documents">
                <thead>
                  <tr>
                    <Th>Type</Th>
                    <Th>Status</Th>
                  </tr>
                </thead>
                <tbody>
                  {bidDocuments.map((doc) => (
                    <tr key={doc.id}>
                      <Td>{doc.doc_type}</Td>
                      <Td>
                        <Badge tone={doc.status === "verified" ? "green" : doc.status === "uploaded" ? "steel" : "neutral"}>{doc.status}</Badge>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No bid documents recorded yet.</p>
            )}
          </Card>

          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Approval workflow</h3>
            {approvalSteps?.length ? (
              <Table ariaLabel="Approval steps">
                <thead>
                  <tr>
                    <Th>Step</Th>
                    <Th>Role required</Th>
                    <Th>Status</Th>
                    <Th />
                  </tr>
                </thead>
                <tbody>
                  {approvalSteps
                    .slice()
                    .sort((a, b) => a.step_order - b.step_order)
                    .map((step) => (
                      <tr key={step.id}>
                        <Td mono>{step.step_order}</Td>
                        <Td>{step.role_required}</Td>
                        <Td>
                          <Badge tone={step.status === "approved" ? "green" : step.status === "rejected" ? "brick" : "amber"}>{step.status}</Badge>
                        </Td>
                        <Td style={{ textAlign: "right" }}>
                          {step.status === "pending" && (
                            <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                              <Button variant="secondary" onClick={() => handleDecideStep(step.id, "approved")} disabled={decideStep.isPending}>
                                Approve
                              </Button>
                              <Button variant="danger" onClick={() => handleDecideStep(step.id, "rejected")} disabled={decideStep.isPending}>
                                Reject
                              </Button>
                            </div>
                          )}
                        </Td>
                      </tr>
                    ))}
                </tbody>
              </Table>
            ) : tender.status === "draft" ? (
              <form onSubmit={handleInitiateApproval}>
                <Field label="Approver roles (comma-separated)" hint="e.g. estimating_manager, finance_director">
                  <Input value={approvalRoles} onChange={(e) => setApprovalRoles(e.target.value)} />
                </Field>
                <Button type="submit" variant="secondary" disabled={initiateApproval.isPending || !approvalRoles.trim()}>
                  Initiate approval workflow
                </Button>
              </form>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No approval steps yet.</p>
            )}

            {(tender.status === "in_approval" || tender.status === "submitted") && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--sf-line)" }}>
                {reopenReason === null ? (
                  <Button variant="ghost" onClick={() => setReopenReason("")}>
                    Reopen for revision
                  </Button>
                ) : (
                  <div>
                    <Field label="Reason for reopening" required>
                      <Input value={reopenReason} onChange={(e) => setReopenReason(e.target.value)} />
                    </Field>
                    <div style={{ display: "flex", gap: 6 }}>
                      <Button variant="secondary" onClick={() => setReopenReason(null)}>
                        Cancel
                      </Button>
                      <Button variant="danger" onClick={handleReopen} disabled={!reopenReason.trim() || reopen.isPending}>
                        Confirm reopen
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 4 }}>RFIs</h3>
            <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 12 }}>
              No list endpoint exists for RFIs on this backend yet — only what you create or respond to in this session
              is shown below; refreshing the page won't preserve it.
            </p>
            <form onSubmit={handleCreateRFI} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <Input required placeholder="Question for the client/consultant" value={rfiQuestion} onChange={(e) => setRfiQuestion(e.target.value)} style={{ flex: 1 }} />
              <Button type="submit" variant="secondary" disabled={createRFI.isPending}>
                Ask
              </Button>
            </form>
            {sessionRFIs.map((rfi) => (
              <div key={rfi.id} style={{ padding: "8px 0", borderTop: "1px solid var(--sf-line)", fontSize: 13 }}>
                <div style={{ fontWeight: 600 }}>{rfi.question}</div>
                {rfi.response ? (
                  <div style={{ marginTop: 4, color: "var(--sf-navy-600)" }}>{rfi.response}</div>
                ) : (
                  <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                    <Input
                      placeholder="Response"
                      value={rfiResponses[rfi.id] ?? ""}
                      onChange={(e) => setRfiResponses({ ...rfiResponses, [rfi.id]: e.target.value })}
                    />
                    <Button variant="secondary" onClick={() => handleRespondRFI(rfi.id)} disabled={respondRFI.isPending}>
                      Respond
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </Card>

          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 4 }}>Clarifications / addenda</h3>
            <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 12 }}>
              Same limitation as RFIs above — no list endpoint yet, session-only display.
            </p>
            <form onSubmit={handleCreateClarification} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 8, marginBottom: 12 }}>
              <Input required placeholder="Addendum #" value={clarificationNumber} onChange={(e) => setClarificationNumber(e.target.value)} />
              <Input required placeholder="Description" value={clarificationDesc} onChange={(e) => setClarificationDesc(e.target.value)} />
              <Button type="submit" variant="secondary" disabled={createClarification.isPending}>
                Add
              </Button>
            </form>
            {sessionClarifications.map((c) => (
              <div key={c.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderTop: "1px solid var(--sf-line)", fontSize: 13 }}>
                <div>
                  <span className="sf-mono">{c.addendum_number}</span> — {c.description}
                </div>
                {c.acknowledged ? (
                  <Badge tone="green">Acknowledged</Badge>
                ) : (
                  <Button variant="ghost" onClick={() => handleAcknowledgeClarification(c.id)} disabled={acknowledgeClarification.isPending}>
                    Acknowledge
                  </Button>
                )}
              </div>
            ))}
          </Card>

          {tender.is_joint_venture && (
            <Card>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>JV partners</h3>
              <form onSubmit={handleAddJVPartner} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 8, marginBottom: 16 }}>
                <Input required placeholder="Partner name" value={jvName} onChange={(e) => setJvName(e.target.value)} />
                <Input required placeholder="Scope %" value={jvScope} onChange={(e) => setJvScope(e.target.value)} />
                <Input required placeholder="Financial %" value={jvFinancial} onChange={(e) => setJvFinancial(e.target.value)} />
                <Button type="submit" variant="secondary" disabled={addJVPartner.isPending}>
                  Add
                </Button>
              </form>
              {jvPartners?.length ? (
                <Table ariaLabel="JV partners">
                  <thead>
                    <tr>
                      <Th>Partner</Th>
                      <Th>Scope %</Th>
                      <Th>Financial %</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {jvPartners.map((p) => (
                      <tr key={p.id}>
                        <Td>{p.partner_name}</Td>
                        <Td mono>{p.scope_share_pct}</Td>
                        <Td mono>{p.financial_share_pct}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No JV partners recorded yet.</p>
              )}
            </Card>
          )}
        </div>

        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Submission readiness</h3>
            {readiness?.can_submit ? (
              <Badge tone="green">Ready to submit</Badge>
            ) : (
              <div>
                <Badge tone="amber">Blocked</Badge>
                <ul style={{ fontSize: 12, marginTop: 10, paddingLeft: 16, color: "var(--sf-navy-600)" }}>
                  {readiness?.blockers?.map((b, i) => (
                    <li key={i} style={{ marginBottom: 4 }}>
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <Button
              style={{ marginTop: 14, width: "100%" }}
              disabled={!readiness?.can_submit || tender.status === "submitted" || tender.status === "awarded" || tender.status === "lost" || submitTender.isPending}
              onClick={() => {
                if (window.confirm("Submit this tender? This locks it in as submitted and starts the evaluation clock.")) handleSubmit();
              }}
            >
              {tender.status === "submitted" ? "Submitted" : "Submit tender"}
            </Button>

            <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--sf-line)" }}>
              <h4 style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 8 }}>Checklist</h4>
              <form onSubmit={handleAddChecklistItem} style={{ display: "flex", gap: 8 }}>
                <Input required placeholder="e.g. Bid bond obtained" value={checklistLabel} onChange={(e) => setChecklistLabel(e.target.value)} />
                <Button type="submit" variant="secondary" disabled={addChecklistItem.isPending}>
                  Add
                </Button>
              </form>
              <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 8 }}>
                Checklist items feed into the blockers list above; there's no list endpoint to display them individually.
              </p>
            </div>
          </Card>

          {tender.status === "submitted" && (
            <Card style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Outcome</h3>
              {outcomeOpen ? (
                <div>
                  <Field label="Outcome" required>
                    <Select value={outcome} onChange={(e) => setOutcome(e.target.value as "won" | "lost")}>
                      <option value="won">Awarded (won)</option>
                      <option value="lost">Lost</option>
                    </Select>
                  </Field>
                  {outcome === "won" && (
                    <Field label="Winning price (optional)">
                      <Input value={winningPrice} onChange={(e) => setWinningPrice(e.target.value)} placeholder="0.00" />
                    </Field>
                  )}
                  <div style={{ display: "flex", gap: 6 }}>
                    <Button variant="secondary" onClick={() => setOutcomeOpen(false)} disabled={recordOutcome.isPending}>
                      Cancel
                    </Button>
                    <Button onClick={handleRecordOutcome} disabled={recordOutcome.isPending}>
                      {recordOutcome.isPending ? "Saving…" : "Save outcome"}
                    </Button>
                  </div>
                </div>
              ) : (
                <Button style={{ width: "100%" }} onClick={() => setOutcomeOpen(true)}>
                  Record outcome
                </Button>
              )}
            </Card>
          )}

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 8 }}>Estimating</h3>
            <p style={{ fontSize: 12, color: "var(--sf-navy-600)", marginBottom: 12 }}>
              Price this tender's BOQ and build the tender price document.
            </p>
            <Link to={`/tenders/${tenderId}/estimate`} style={{ fontSize: 13, fontWeight: 600 }}>
              Open estimate →
            </Link>
          </Card>
        </div>
      </div>
    </div>
  );
}
