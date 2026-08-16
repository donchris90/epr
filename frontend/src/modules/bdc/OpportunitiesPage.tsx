import { useState } from "react";
import { Card, PageHeader, Badge, Button, formatMoney, Input, Field } from "../../components/ui";
import { useOpportunities, useTransitionOpportunity, useBidNoBidDecision } from "./hooks";

const STAGES: { key: string; label: string; next?: string }[] = [
  { key: "identified", label: "Identified", next: "qualified" },
  { key: "qualified", label: "Qualified", next: "bid_no_bid" },
  { key: "bid_no_bid", label: "Bid / No-Bid", next: "submitted" },
  { key: "submitted", label: "Submitted" },
  { key: "won", label: "Won" },
  { key: "lost", label: "Lost" },
];

export default function OpportunitiesPage() {
  const { data: opportunities, isLoading } = useOpportunities();
  const transition = useTransitionOpportunity();
  const decide = useBidNoBidDecision();
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [rationale, setRationale] = useState("");
  const [reasonCode, setReasonCode] = useState("");

  const byStage = (stage: string) => (opportunities || []).filter((o) => o.stage === stage);

  async function handleDecision(id: string, decision: "bid" | "no_bid") {
    await decide.mutateAsync({ id, decision, rationale, reasonCode: decision === "no_bid" ? reasonCode : undefined });
    setDecidingId(null);
    setRationale("");
    setReasonCode("");
  }

  return (
    <div>
      <PageHeader eyebrow="Business Development" title="Opportunity pipeline" />

      {isLoading ? (
        <p>Loading…</p>
      ) : (
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
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{opp.name}</div>
                    <div className="sf-mono" style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 8 }}>
                      {formatMoney(opp.estimated_value, opp.currency)}
                    </div>

                    {stage.key === "bid_no_bid" && decidingId === opp.id ? (
                      <div>
                        <Field label="Rationale">
                          <Input value={rationale} onChange={(e) => setRationale(e.target.value)} />
                        </Field>
                        <Field label="No-bid reason (if declining)">
                          <Input value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} />
                        </Field>
                        <div style={{ display: "flex", gap: 6 }}>
                          <Button variant="secondary" onClick={() => handleDecision(opp.id, "bid")} disabled={!rationale}>
                            Bid
                          </Button>
                          <Button variant="danger" onClick={() => handleDecision(opp.id, "no_bid")} disabled={!rationale || !reasonCode}>
                            No-bid
                          </Button>
                        </div>
                      </div>
                    ) : stage.key === "bid_no_bid" ? (
                      <Button variant="ghost" onClick={() => setDecidingId(opp.id)}>
                        Record decision →
                      </Button>
                    ) : stage.next ? (
                      <Button
                        variant="ghost"
                        onClick={() => transition.mutate({ id: opp.id, newStage: stage.next! })}
                        disabled={transition.isPending}
                      >
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
      )}
    </div>
  );
}
