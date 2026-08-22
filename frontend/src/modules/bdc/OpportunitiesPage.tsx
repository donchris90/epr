import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, PageHeader, Badge, Button, formatMoney, Input, Field } from "../../components/ui";
import { QueryState } from "../../components/QueryState";
import { useOpportunities, useTransitionOpportunity, useBidNoBidDecision } from "./hooks";
import { useToast } from "../../lib/toast";
import { getErrorMessage } from "../../api/client";

const STAGES: { key: string; label: string; next?: string }[] = [
  { key: "identified", label: "Identified", next: "qualified" },
  { key: "qualified", label: "Qualified", next: "bid_no_bid" },
  { key: "bid_no_bid", label: "Bid / No-Bid", next: "submitted" },
  { key: "submitted", label: "Submitted" },
  { key: "won", label: "Won" },
  { key: "lost", label: "Lost" },
];

export default function OpportunitiesPage() {
  const query = useOpportunities();
  const transition = useTransitionOpportunity();
  const decide = useBidNoBidDecision();
  const toast = useToast();
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [rationale, setRationale] = useState("");
  const [reasonCode, setReasonCode] = useState("");
  const [scores, setScores] = useState({ capability_fit: "3", profitability: "3", strategic_value: "3" });
  const [search, setSearch] = useState("");

  async function handleDecision(id: string, decision: "bid" | "no_bid") {
    try {
      await decide.mutateAsync({
        id,
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
      setDecidingId(null);
      setRationale("");
      setReasonCode("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleAdvance(id: string, nextStage: string) {
    try {
      await transition.mutateAsync({ id, newStage: nextStage });
    } catch (err) {
      // Surfaces real backend rules verbatim -- e.g. moving to "won"
      // requires a linked Contract record from Module 4, which
      // doesn't exist yet in this codebase, so that transition will
      // always 409 with a clear explanation from the backend today.
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Business Development" title="Opportunity pipeline" />

      <div style={{ maxWidth: 320, marginBottom: 16 }}>
        <label className="sf-visually-hidden" htmlFor="opportunity-search">
          Search opportunities
        </label>
        <Input id="opportunity-search" placeholder="Search opportunities…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <QueryState query={query} variant="dashboard" loadingLabel="Loading opportunities" emptyTitle="No opportunities yet">
        {(opportunities) => {
          const filtered = search.trim()
            ? opportunities.filter((o) => o.name.toLowerCase().includes(search.trim().toLowerCase()))
            : opportunities;
          const byStage = (stage: string) => filtered.filter((o) => o.stage === stage);

          return (
            <div style={{ display: "flex", gap: 14, overflowX: "auto", paddingBottom: 8 }}>
              {STAGES.map((stage) => (
                <div key={stage.key} style={{ minWidth: 240, flex: "0 0 240px" }}>
                  <div
                    className="sf-mono"
                    style={{
                      fontSize: 11,
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                      color: "var(--sf-navy-400)",
                      marginBottom: 8,
                      display: "flex",
                      justifyContent: "space-between",
                    }}
                  >
                    <span>{stage.label}</span>
                    <span>{byStage(stage.key).length}</span>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {byStage(stage.key).map((opp) => (
                      <Card key={opp.id} style={{ padding: 12 }}>
                        <Link to={`/business-development/opportunities/${opp.id}`} style={{ textDecoration: "none", color: "inherit" }}>
                          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{opp.name}</div>
                        </Link>
                        <div className="sf-mono" style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 8 }}>
                          {formatMoney(opp.estimated_value, opp.currency)}
                        </div>

                        {stage.key === "bid_no_bid" && decidingId === opp.id ? (
                          <div>
                            <Field label="Rationale" required>
                              <Input value={rationale} onChange={(e) => setRationale(e.target.value)} />
                            </Field>
                            <div style={{ display: "flex", gap: 6 }}>
                              <Field label="Capability fit (1–5)">
                                <Input
                                  type="number"
                                  min={1}
                                  max={5}
                                  value={scores.capability_fit}
                                  onChange={(e) => setScores({ ...scores, capability_fit: e.target.value })}
                                />
                              </Field>
                              <Field label="Profitability (1–5)">
                                <Input
                                  type="number"
                                  min={1}
                                  max={5}
                                  value={scores.profitability}
                                  onChange={(e) => setScores({ ...scores, profitability: e.target.value })}
                                />
                              </Field>
                              <Field label="Strategic value (1–5)">
                                <Input
                                  type="number"
                                  min={1}
                                  max={5}
                                  value={scores.strategic_value}
                                  onChange={(e) => setScores({ ...scores, strategic_value: e.target.value })}
                                />
                              </Field>
                            </div>
                            <Field label="No-bid reason (if declining)">
                              <Input value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} />
                            </Field>
                            <div style={{ display: "flex", gap: 6 }}>
                              <Button variant="secondary" onClick={() => handleDecision(opp.id, "bid")} disabled={!rationale || decide.isPending}>
                                Bid
                              </Button>
                              <Button
                                variant="danger"
                                onClick={() => handleDecision(opp.id, "no_bid")}
                                disabled={!rationale || !reasonCode || decide.isPending}
                              >
                                No-bid
                              </Button>
                            </div>
                          </div>
                        ) : stage.key === "bid_no_bid" ? (
                          <Button variant="ghost" onClick={() => setDecidingId(opp.id)}>
                            Record decision →
                          </Button>
                        ) : stage.next ? (
                          <Button variant="ghost" onClick={() => handleAdvance(opp.id, stage.next!)} disabled={transition.isPending}>
                            Advance →
                          </Button>
                        ) : stage.key === "won" ? (
                          <Badge tone="green">Awarded</Badge>
                        ) : (
                          <Badge tone="brick">Closed</Badge>
                        )}
                      </Card>
                    ))}
                    {byStage(stage.key).length === 0 && (
                      <div style={{ fontSize: 12, color: "var(--sf-navy-400)", padding: "8px 0" }}>—</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          );
        }}
      </QueryState>
    </div>
  );
}
