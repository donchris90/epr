import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { ProjectSelect } from "../../components/ProjectSelect";
import { useDelayEvents, useCreateDelayEvent } from "./hooks";

const CAUSES = [
  { value: "weather", label: "Weather" },
  { value: "client_instruction", label: "Client instruction" },
  { value: "design_change", label: "Design change" },
  { value: "resource_shortage", label: "Resource shortage" },
  { value: "other", label: "Other" },
];

export default function DelayEventsPage() {
  const [projectId, setProjectId] = useState("");
  const { data: events, isLoading } = useDelayEvents(projectId || undefined);
  const createEvent = useCreateDelayEvent();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    activity_id: "",
    cause_classification: "weather",
    description: "",
    delay_days: "",
    occurred_on: "",
  });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createEvent.mutateAsync({
      project_id: projectId || undefined,
      activity_id: form.activity_id || undefined,
      cause_classification: form.cause_classification,
      description: form.description,
      delay_days: Number(form.delay_days),
      occurred_on: form.occurred_on,
    });
    setForm({ activity_id: "", cause_classification: "weather", description: "", delay_days: "", occurred_on: "" });
    setShowForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Project Planning"
        title="Delay Events"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "Log delay event"}</Button>}
      />

      <div style={{ marginBottom: 20, maxWidth: 320 }}>
        <Field label="Filter by project ID">
          <ProjectSelect value={projectId} onChange={setProjectId} />
        </Field>
      </div>

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
              <Field label="Cause">
                <select
                  value={form.cause_classification}
                  onChange={(e) => setForm({ ...form, cause_classification: e.target.value })}
                  style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, width: "100%", background: "#fff" }}
                >
                  {CAUSES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Delay (days)">
                <Input
                  required
                  type="number"
                  min={1}
                  value={form.delay_days}
                  onChange={(e) => setForm({ ...form, delay_days: e.target.value })}
                />
              </Field>
              <Field label="Occurred on">
                <Input
                  required
                  type="date"
                  value={form.occurred_on}
                  onChange={(e) => setForm({ ...form, occurred_on: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Affected activity ID (optional)">
              <Input
                placeholder="Activity UUID, if this delay is tied to one"
                value={form.activity_id}
                onChange={(e) => setForm({ ...form, activity_id: e.target.value })}
              />
            </Field>
            <Field label="Description">
              <Input
                required
                placeholder="What happened, and its schedule impact"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </Field>
            <Button type="submit" disabled={createEvent.isPending}>
              {createEvent.isPending ? "Recording…" : "Record delay event"}
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !events?.length ? (
        <EmptyState title="No delay events logged" hint="Delay events tied to the critical path are automatically flagged for review." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Date</Th>
                <Th>Cause</Th>
                <Th>Description</Th>
                <Th>Delay</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev: any) => (
                <tr key={ev.id}>
                  <Td mono>{new Date(ev.occurred_on).toLocaleDateString()}</Td>
                  <Td>{CAUSES.find((c) => c.value === ev.cause_classification)?.label ?? ev.cause_classification}</Td>
                  <Td>{ev.description}</Td>
                  <Td mono>{ev.delay_days}d</Td>
                  <Td>
                    {ev.affected_critical_path && <Badge tone="brick">Critical path</Badge>}
                    {ev.flagged_for_review && <Badge tone="amber">Flagged</Badge>}
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
