import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { ProjectSelect } from "../../components/ProjectSelect";
import { useIncidents, useCreateIncident, useCloseIncident, useCreateNearMiss, useSafetyIndicators } from "./hooks";

const CLASSIFICATIONS = ["first_aid", "medical_treatment", "lost_time", "fatality"];

export default function IncidentsPage() {
  const { data: incidents, isLoading } = useIncidents();
  const createIncident = useCreateIncident();
  const closeIncident = useCloseIncident();
  const createNearMiss = useCreateNearMiss();

  const [showIncidentForm, setShowIncidentForm] = useState(false);
  const [incidentForm, setIncidentForm] = useState({ classification: "first_aid", description: "" });

  const [showNearMissForm, setShowNearMissForm] = useState(false);
  const [nearMissForm, setNearMissForm] = useState({ classification: "first_aid", description: "" });

  const [projectId, setProjectId] = useState("");
  const { data: indicators } = useSafetyIndicators(projectId || undefined);

  async function handleCreateIncident(e: React.FormEvent) {
    e.preventDefault();
    await createIncident.mutateAsync(incidentForm);
    setIncidentForm({ classification: "first_aid", description: "" });
    setShowIncidentForm(false);
  }

  async function handleCreateNearMiss(e: React.FormEvent) {
    e.preventDefault();
    await createNearMiss.mutateAsync(nearMissForm);
    setNearMissForm({ classification: "first_aid", description: "" });
    setShowNearMissForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Health, Safety & Environment"
        title="Incidents & Near Misses"
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" onClick={() => setShowNearMissForm((v) => !v)}>
              {showNearMissForm ? "Cancel" : "Log near miss"}
            </Button>
            <Button onClick={() => setShowIncidentForm((v) => !v)}>{showIncidentForm ? "Cancel" : "Log incident"}</Button>
          </div>
        }
      />

      <div style={{ marginBottom: 20, maxWidth: 320 }}>
        <Field label="Project (for safety indicators)">
          <ProjectSelect value={projectId} onChange={setProjectId} />
        </Field>
      </div>

      {indicators && (
        <Card style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 32 }}>
            <div>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>TRIR</div>
              <div className="sf-mono" style={{ fontSize: 22, fontWeight: 700 }}>{indicators.trir ?? "—"}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>LTIFR</div>
              <div className="sf-mono" style={{ fontSize: 22, fontWeight: 700 }}>{indicators.ltifr ?? "—"}</div>
            </div>
          </div>
        </Card>
      )}

      {showIncidentForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreateIncident} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 12 }}>
            <select
              aria-label="Incident classification"
              value={incidentForm.classification}
              onChange={(e) => setIncidentForm({ ...incidentForm, classification: e.target.value })}
              style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
            >
              {CLASSIFICATIONS.map((c) => (
                <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
              ))}
            </select>
            <Input required placeholder="Description" value={incidentForm.description} onChange={(e) => setIncidentForm({ ...incidentForm, description: e.target.value })} />
            <Button type="submit" disabled={createIncident.isPending} style={{ height: 38, alignSelf: "end" }}>Log</Button>
          </form>
        </Card>
      )}

      {showNearMissForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreateNearMiss} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 12 }}>
            <select
              aria-label="Near miss classification"
              value={nearMissForm.classification}
              onChange={(e) => setNearMissForm({ ...nearMissForm, classification: e.target.value })}
              style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
            >
              {CLASSIFICATIONS.map((c) => (
                <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
              ))}
            </select>
            <Input required placeholder="Description" value={nearMissForm.description} onChange={(e) => setNearMissForm({ ...nearMissForm, description: e.target.value })} />
            <Button type="submit" disabled={createNearMiss.isPending} style={{ height: 38, alignSelf: "end" }}>Log</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !incidents?.length ? (
        <EmptyState title="No incidents logged" hint="Every recordable incident here automatically generates a linked corrective action in Quality Management." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead><tr><Th>Classification</Th><Th>Description</Th><Th>Status</Th><Th></Th></tr></thead>
            <tbody>
              {incidents.map((i: any) => (
                <tr key={i.id}>
                  <Td><Badge tone={i.classification === "fatality" ? "brick" : "amber"}>{i.classification.replace(/_/g, " ")}</Badge></Td>
                  <Td>{i.description}</Td>
                  <Td><Badge tone={i.status === "closed" ? "green" : "neutral"}>{i.status}</Badge></Td>
                  <Td>
                    {i.status !== "closed" && (
                      <button onClick={() => closeIncident.mutate(i.id)} style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                        Close
                      </button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
