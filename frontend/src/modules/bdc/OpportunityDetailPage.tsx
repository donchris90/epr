import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Select, formatMoney } from "../../components/ui";
import { LoadingState } from "../../components/Loading";
import { ErrorState } from "../../components/ErrorState";
import { Modal } from "../../components/Modal";
import {
  useBidNoBidDecision,
  useClient,
  useLead,
  useOpportunity,
  useRecordWinLoss,
  useTransitionOpportunity,
} from "./hooks";
import { useCreateTender, useTenders } from "../tbm/hooks";
import { useToast } from "../../lib/toast";
import { getErrorMessage } from "../../api/client";
import type { OpportunityStage } from "./types";

const STAGE_ORDER: OpportunityStage[] = ["identified", "qualified", "bid_no_bid", "submitted", "won"];
const STAGE_LABELS: Record<OpportunityStage, string> = {
  identified: "Identified",
  qualified: "Qualified",
  bid_no_bid: "Bid / No-Bid",
  submitted: "Submitted",
  won: "Won",
  lost: "Lost",
};
// Mirrors _ALLOWED_TRANSITIONS in backend/app/modules/bdc/services.py --
// the backend is the source of truth and rejects anything else with a
// 409; this is only used to decide which button to show, not to
// enforce the rule (that always happens server-side).
const NEXT_STAGE: Partial<Record<OpportunityStage, OpportunityStage>> = {
  identified: "qualified",
  qualified: "bid_no_bid",
  bid_no_bid: "submitted",
  submitted: "won",
};

function PipelineStepper({ stage }: { stage: OpportunityStage }) {
  if (stage === "lost") {
    return <Badge tone="brick">Closed — Lost</Badge>;
  }
  const currentIndex = STAGE_ORDER.indexOf(stage);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
      {STAGE_ORDER.map((s, i) => (
        <div key={s} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div
            style={{
              padding: "4px 10px",
              borderRadius: 999,
              fontSize: 12,
              fontWeight: 600,
              background: i <= currentIndex ? "var(--sf-amber)" : "var(--sf-paper-dim)",
              color: i <= currentIndex ? "var(--sf-navy-900)" : "var(--sf-navy-400)",
              border: i === currentIndex ? "2px solid var(--sf-navy-900)" : "2px solid transparent",
            }}
          >
            {STAGE_LABELS[s]}
          </div>
          {i < STAGE_ORDER.length - 1 && (
            <span aria-hidden="true" style={{ color: "var(--sf-navy-400)" }}>
              →
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function CreateTenderModal({ opportunityId, defaultRef, onClose, onDone }: { opportunityId: string; defaultRef: string; onClose: () => void; onDone: (id: string) => void }) {
  const createTender = useCreateTender();
  const toast = useToast();
  const [referenceNumber, setReferenceNumber] = useState(defaultRef);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!referenceNumber.trim()) {
      setError("Reference number is required.");
      return;
    }
    setError(null);
    try {
      const res = await createTender.mutateAsync({ opportunity_id: opportunityId, reference_number: referenceNumber.trim() });
      toast.success(`Tender "${referenceNumber.trim()}" was created.`);
      onDone(res.data.id);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Modal title="Create tender for this opportunity" onClose={onClose}>
      <Field label="Reference number" required error={error ?? undefined}>
        <Input value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} placeholder="e.g. TND-2026-014" />
      </Field>
      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <Button variant="secondary" onClick={onClose} disabled={createTender.isPending}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={createTender.isPending}>
          {createTender.isPending ? "Creating…" : "Create tender"}
        </Button>
      </div>
    </Modal>
  );
}

export default function OpportunityDetailPage() {
  const { opportunityId } = useParams<{ opportunityId: string }>();
  const navigate = useNavigate();
  const opportunity = useOpportunity(opportunityId);
  const client = useClient(opportunity.data?.client_id);
  const lead = useLead(opportunity.data?.lead_id ?? undefined);
  const tenders = useTenders();
  const transition = useTransitionOpportunity();
  const bidNoBid = useBidNoBidDecision();
  const winLoss = useRecordWinLoss();
  const toast = useToast();

  const [decisionOpen, setDecisionOpen] = useState(false);
  const [decision, setDecision] = useState<"bid" | "no_bid">("bid");
  const [rationale, setRationale] = useState("");
  const [reasonCode, setReasonCode] = useState("");
  const [scores, setScores] = useState({ capability_fit: "3", profitability: "3", strategic_value: "3" });

  const [outcomeOpen, setOutcomeOpen] = useState(false);
  const [outcome, setOutcome] = useState<"won" | "lost">("won");
  const [winningPrice, setWinningPrice] = useState("");
  const [outcomeReasonCode, setOutcomeReasonCode] = useState("");

  const [showCreateTender, setShowCreateTender] = useState(false);

  if (opportunity.isLoading) {
    return (
      <div>
        <PageHeader eyebrow="Business Development" title="Opportunity" />
        <LoadingState variant="detail" label="Loading opportunity" />
      </div>
    );
  }

  if (opportunity.isError) {
    return (
      <div>
        <PageHeader eyebrow="Business Development" title="Opportunity" />
        <ErrorState error={opportunity.error} onRetry={() => opportunity.refetch()} />
      </div>
    );
  }

  if (!opportunity.data) {
    return (
      <div>
        <PageHeader eyebrow="Business Development" title="Opportunity not found" />
        <EmptyState title="Opportunity not found" hint="It may have been removed, or the link is out of date." />
      </div>
    );
  }

  const o = opportunity.data;
  const relatedTenders = (tenders.data ?? []).filter((t) => t.opportunity_id === o.id);
  const next = NEXT_STAGE[o.stage];

  async function handleAdvance() {
    if (!opportunityId || !next) return;
    try {
      await transition.mutateAsync({ id: opportunityId, newStage: next });
      toast.success(`Moved to ${STAGE_LABELS[next]}.`);
    } catch (err) {
      // Real backend rule, surfaced verbatim: moving to "won" requires
      // a linked Contract (Module 4), which doesn't exist in this
      // codebase yet -- so this transition will always 409 today.
      toast.error(getErrorMessage(err));
    }
  }

  async function handleClose() {
    if (!opportunityId || o.stage === "won" || o.stage === "lost") return;
    try {
      await transition.mutateAsync({ id: opportunityId, newStage: "lost" });
      toast.success("Opportunity closed as Lost.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function submitDecision() {
    if (!opportunityId || !rationale) return;
    try {
      await bidNoBid.mutateAsync({
        id: opportunityId,
        decision,
        rationale,
        reasonCode: decision === "no_bid" ? reasonCode : undefined,
        scorecard: {
          capability_fit: Number(scores.capability_fit),
          profitability: Number(scores.profitability),
          strategic_value: Number(scores.strategic_value),
        },
      });
      toast.success(decision === "bid" ? "Recorded a Bid decision." : "Recorded a No-Bid decision.");
      setDecisionOpen(false);
      setRationale("");
      setReasonCode("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function submitOutcome() {
    if (!opportunityId) return;
    try {
      await winLoss.mutateAsync({
        id: opportunityId,
        outcome,
        winningPrice: winningPrice || undefined,
        reasonCode: outcome === "lost" ? outcomeReasonCode || undefined : undefined,
      });
      toast.success(`Recorded as ${outcome === "won" ? "Won" : "Lost"}.`);
      setOutcomeOpen(false);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div style={{ maxWidth: 1000 }}>
      <PageHeader eyebrow="Business Development · Opportunity" title={o.name} />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--sf-navy-400)", marginBottom: 12 }}>PIPELINE STAGE</div>
        <PipelineStepper stage={o.stage} />

        <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
          {o.stage === "bid_no_bid" && (
            <Button onClick={() => setDecisionOpen(true)}>Record Bid/No-Bid decision</Button>
          )}
          {o.stage !== "bid_no_bid" && next && (
            <Button variant="secondary" onClick={handleAdvance} disabled={transition.isPending}>
              Advance to {STAGE_LABELS[next]} →
            </Button>
          )}
          {o.stage === "submitted" && (
            <Button variant="secondary" onClick={() => setOutcomeOpen(true)}>
              Record outcome
            </Button>
          )}
          {o.stage !== "won" && o.stage !== "lost" && (
            <Button variant="danger" onClick={handleClose} disabled={transition.isPending}>
              Close as Lost
            </Button>
          )}
        </div>
        {o.stage === "submitted" && next === "won" && (
          <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 10 }}>
            Note: moving directly to "Won" requires a linked Contract record, which isn't available in this deployment
            yet — use "Record outcome" instead, which records the win/loss result without requiring a contract.
          </div>
        )}
      </Card>

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        <Card>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--sf-navy-400)", marginBottom: 10 }}>DETAILS</div>
          <dl style={{ fontSize: 13, margin: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--sf-line)" }}>
              <dt style={{ color: "var(--sf-navy-400)" }}>Estimated value</dt>
              <dd style={{ margin: 0 }} className="sf-mono">
                {formatMoney(o.estimated_value, o.currency)}
              </dd>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--sf-line)" }}>
              <dt style={{ color: "var(--sf-navy-400)" }}>Submission deadline</dt>
              <dd style={{ margin: 0 }} className="sf-mono">
                {o.submission_deadline ? new Date(o.submission_deadline).toLocaleDateString() : "—"}
              </dd>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--sf-line)" }}>
              <dt style={{ color: "var(--sf-navy-400)" }}>Bid/No-Bid decision</dt>
              <dd style={{ margin: 0 }}>{o.bid_no_bid_decision ?? "—"}</dd>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
              <dt style={{ color: "var(--sf-navy-400)" }}>Logged</dt>
              <dd style={{ margin: 0 }} className="sf-mono">
                {new Date(o.created_at).toLocaleDateString()}
              </dd>
            </div>
          </dl>
        </Card>

        <Card>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--sf-navy-400)", marginBottom: 10 }}>RELATED</div>
          <div style={{ fontSize: 13, marginBottom: 10 }}>
            <div style={{ color: "var(--sf-navy-400)", fontSize: 11, marginBottom: 2 }}>Client</div>
            {client.data ? (
              <Link to={`/business-development/clients/${client.data.id}`}>{client.data.name}</Link>
            ) : client.isLoading ? (
              "…"
            ) : (
              "—"
            )}
          </div>
          <div style={{ fontSize: 13 }}>
            <div style={{ color: "var(--sf-navy-400)", fontSize: 11, marginBottom: 2 }}>Originating lead</div>
            {o.lead_id ? (
              lead.data ? (
                <Link to={`/business-development/leads/${lead.data.id}`}>{lead.data.name}</Link>
              ) : (
                "…"
              )
            ) : (
              "Created directly (not from a lead)"
            )}
          </div>
        </Card>
      </div>

      <Card style={{ padding: 0 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "12px 16px",
            borderBottom: "1px solid var(--sf-line)",
          }}
        >
          <span style={{ fontWeight: 700, fontSize: 13 }}>Related tenders</span>
          <Button variant="ghost" onClick={() => setShowCreateTender(true)}>
            + Create tender
          </Button>
        </div>
        {tenders.isLoading ? (
          <LoadingState variant="table" label="Loading tenders" rows={2} />
        ) : relatedTenders.length === 0 ? (
          <div style={{ padding: 20 }}>
            <EmptyState
              title="No tenders yet"
              hint="Once this opportunity is ready to bid, create a tender to start tracking the submission."
              action={<Button onClick={() => setShowCreateTender(true)}>+ Create tender</Button>}
            />
          </div>
        ) : (
          <div style={{ padding: "8px 16px" }}>
            {relatedTenders.map((t) => (
              <div
                key={t.id}
                style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--sf-line)", fontSize: 13 }}
              >
                <Link to={`/tenders/${t.id}`} className="sf-mono">
                  {t.reference_number}
                </Link>
                <span>{t.status}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {decisionOpen && (
        <Modal title="Bid / No-Bid decision" onClose={() => setDecisionOpen(false)}>
          <Field label="Decision" required>
            <Select value={decision} onChange={(e) => setDecision(e.target.value as "bid" | "no_bid")}>
              <option value="bid">Bid</option>
              <option value="no_bid">No-Bid</option>
            </Select>
          </Field>
          <Field label="Rationale" required>
            <Input value={rationale} onChange={(e) => setRationale(e.target.value)} />
          </Field>
          <div style={{ display: "flex", gap: 6 }}>
            <Field label="Capability fit (1–5)">
              <Input type="number" min={1} max={5} value={scores.capability_fit} onChange={(e) => setScores({ ...scores, capability_fit: e.target.value })} />
            </Field>
            <Field label="Profitability (1–5)">
              <Input type="number" min={1} max={5} value={scores.profitability} onChange={(e) => setScores({ ...scores, profitability: e.target.value })} />
            </Field>
            <Field label="Strategic value (1–5)">
              <Input type="number" min={1} max={5} value={scores.strategic_value} onChange={(e) => setScores({ ...scores, strategic_value: e.target.value })} />
            </Field>
          </div>
          {decision === "no_bid" && (
            <Field label="No-bid reason code" required>
              <Input value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} placeholder="e.g. capacity, risk, margin" />
            </Field>
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
            <Button variant="secondary" onClick={() => setDecisionOpen(false)} disabled={bidNoBid.isPending}>
              Cancel
            </Button>
            <Button onClick={submitDecision} disabled={!rationale || (decision === "no_bid" && !reasonCode) || bidNoBid.isPending}>
              {bidNoBid.isPending ? "Saving…" : "Save decision"}
            </Button>
          </div>
        </Modal>
      )}

      {outcomeOpen && (
        <Modal title="Record tender outcome" onClose={() => setOutcomeOpen(false)}>
          <Field label="Outcome" required>
            <Select value={outcome} onChange={(e) => setOutcome(e.target.value as "won" | "lost")}>
              <option value="won">Won</option>
              <option value="lost">Lost</option>
            </Select>
          </Field>
          {outcome === "won" && (
            <Field label="Winning price (optional)">
              <Input value={winningPrice} onChange={(e) => setWinningPrice(e.target.value)} placeholder="0.00" />
            </Field>
          )}
          {outcome === "lost" && (
            <Field label="Reason code (optional)">
              <Input value={outcomeReasonCode} onChange={(e) => setOutcomeReasonCode(e.target.value)} placeholder="e.g. price, technical" />
            </Field>
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
            <Button variant="secondary" onClick={() => setOutcomeOpen(false)} disabled={winLoss.isPending}>
              Cancel
            </Button>
            <Button onClick={submitOutcome} disabled={winLoss.isPending}>
              {winLoss.isPending ? "Saving…" : "Save outcome"}
            </Button>
          </div>
        </Modal>
      )}

      {showCreateTender && opportunityId && (
        <CreateTenderModal
          opportunityId={opportunityId}
          defaultRef={`TND-${o.name.slice(0, 12).toUpperCase().replace(/\s+/g, "-")}`}
          onClose={() => setShowCreateTender(false)}
          onDone={(tenderId) => {
            setShowCreateTender(false);
            navigate(`/tenders/${tenderId}`);
          }}
        />
      )}
    </div>
  );
}
