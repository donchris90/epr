import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { useITPs, useCreateITP, useHoldPoints, useAddHoldPoint, useRecordHoldPointResult, useApproveConcession } from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  pending: "amber",
  passed: "green",
  failed: "brick",
  concession_approved: "steel",
};

export default function ITPsPage() {
  const { data: itps, isLoading } = useITPs();
  const createITP = useCreateITP();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ activity_type: "", title: "" });

  const [selectedITP, setSelectedITP] = useState<string | null>(null);
  const { data: holdPoints } = useHoldPoints(selectedITP || undefined);
  const addHoldPoint = useAddHoldPoint(selectedITP || undefined);
  const [hpForm, setHpForm] = useState({ sequence_order: "1", description: "" });
  const recordResult = useRecordHoldPointResult();
  const approveConcession = useApproveConcession();
  const [concessionReason, setConcessionReason] = useState<Record<string, string>>({});

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createITP.mutateAsync(form);
    setForm({ activity_type: "", title: "" });
    setShowForm(false);
  }

  async function handleAddHoldPoint(e: React.FormEvent) {
    e.preventDefault();
    await addHoldPoint.mutateAsync({ sequence_order: Number(hpForm.sequence_order), description: hpForm.description });
    setHpForm({ sequence_order: String(Number(hpForm.sequence_order) + 1), description: "" });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Quality Management"
        title="Inspection & Test Plans"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New ITP"}</Button>}
      />

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate} style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 12 }}>
            <Field label="Activity type">
              <Input required value={form.activity_type} onChange={(e) => setForm({ ...form, activity_type: e.target.value })} placeholder="e.g. Concrete pour" />
            </Field>
            <Field label="Title">
              <Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createITP.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !itps?.length ? (
        <EmptyState title="No ITPs yet" hint="Create one, then define sequenced hold points that gate progress." />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 20 }}>
          <Card style={{ padding: 0 }}>
            <Table>
              <thead><tr><Th>Title</Th></tr></thead>
              <tbody>
                {itps.map((itp: any) => (
                  <tr
                    key={itp.id}
                    onClick={() => setSelectedITP(itp.id)}
                    style={{ cursor: "pointer", background: selectedITP === itp.id ? "var(--sf-paper-dim)" : undefined }}
                  >
                    <Td>
                      <div>{itp.title}</div>
                      <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>{itp.activity_type}</div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 4 }}>
              {selectedITP ? "Hold points" : "Select an ITP to view hold points"}
            </h3>
            {selectedITP && (
              <>
                <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
                  A mandatory hold point that hasn't passed blocks progress — a concession requires a documented
                  reason and is the only way around a still-pending mandatory hold.
                </p>
                {holdPoints?.length ? (
                  <Table>
                    <thead><tr><Th>#</Th><Th>Description</Th><Th>Status</Th><Th></Th></tr></thead>
                    <tbody>
                      {holdPoints.map((hp: any) => (
                        <tr key={hp.id}>
                          <Td mono>{hp.sequence_order}</Td>
                          <Td>
                            {hp.description}
                            {hp.is_mandatory_hold && <Badge tone="brick">Mandatory</Badge>}
                          </Td>
                          <Td><Badge tone={STATUS_TONE[hp.status] ?? "neutral"}>{hp.status}</Badge></Td>
                          <Td>
                            {hp.status === "pending" && (
                              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                                <button onClick={() => recordResult.mutate({ holdPointId: hp.id, passed: true })} style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Pass</button>
                                <button onClick={() => recordResult.mutate({ holdPointId: hp.id, passed: false })} style={{ background: "none", border: "none", color: "var(--sf-brick)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Fail</button>
                                <Input
                                  placeholder="Concession reason"
                                  value={concessionReason[hp.id] || ""}
                                  onChange={(e) => setConcessionReason({ ...concessionReason, [hp.id]: e.target.value })}
                                  style={{ width: 140, fontSize: 11 }}
                                />
                                <button
                                  disabled={!concessionReason[hp.id]}
                                  onClick={() => approveConcession.mutate({ holdPointId: hp.id, reason: concessionReason[hp.id] })}
                                  style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                                >
                                  Concede
                                </button>
                              </div>
                            )}
                          </Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                ) : (
                  <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>No hold points defined yet.</p>
                )}
                <form onSubmit={handleAddHoldPoint} style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 8, marginTop: 12 }}>
                  <Input required placeholder="Sequence #" value={hpForm.sequence_order} onChange={(e) => setHpForm({ ...hpForm, sequence_order: e.target.value })} />
                  <Input required placeholder="Description" value={hpForm.description} onChange={(e) => setHpForm({ ...hpForm, description: e.target.value })} />
                  <Button type="submit" disabled={addHoldPoint.isPending}>Add</Button>
                </form>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
