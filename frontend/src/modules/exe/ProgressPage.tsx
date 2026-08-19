import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, EmptyState, Input, Field, Select } from "../../components/ui";
import { useProgressEntries, useAddProgressEntry } from "./hooks";

const MEASUREMENT_TYPES = [
  { value: "percentage", label: "Percentage complete" },
  { value: "quantity", label: "Quantity" },
];

export default function ProgressPage() {
  const [activityFilter, setActivityFilter] = useState("");
  const { data: entries, isLoading } = useProgressEntries(activityFilter || undefined);
  const addEntry = useAddProgressEntry();

  const [form, setForm] = useState({ activity_id: "", measurement_type: "percentage", value: "", unit: "" });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await addEntry.mutateAsync({
      activity_id: form.activity_id,
      measurement_type: form.measurement_type,
      value: form.value,
      unit: form.unit || undefined,
    });
    setForm({ activity_id: form.activity_id, measurement_type: "percentage", value: "", unit: "" });
  }

  return (
    <div>
      <PageHeader eyebrow="Project Execution" title="Progress" />

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Record progress against an activity</h3>
        <form onSubmit={handleSubmit}>
          <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 16 }}>
            <Field label="Activity ID">
              <Input
                required
                placeholder="WBS activity UUID"
                value={form.activity_id}
                onChange={(e) => setForm({ ...form, activity_id: e.target.value })}
              />
            </Field>
            <Field label="Measurement">
              <Select
                value={form.measurement_type}
                onChange={(e) => setForm({ ...form, measurement_type: e.target.value })}
              >
                {MEASUREMENT_TYPES.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Value">
              <Input
                required
                placeholder={form.measurement_type === "percentage" ? "e.g. 65" : "e.g. 120"}
                value={form.value}
                onChange={(e) => setForm({ ...form, value: e.target.value })}
              />
            </Field>
            <Field label="Unit (optional)">
              <Input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} placeholder="m3, %" />
            </Field>
          </div>
          <Button type="submit" disabled={addEntry.isPending}>
            {addEntry.isPending ? "Recording…" : "Record progress"}
          </Button>
        </form>
      </Card>

      <div style={{ marginBottom: 16, maxWidth: 320 }}>
        <Field label="Filter by activity ID">
          <Input
            placeholder="Paste an activity UUID"
            value={activityFilter}
            onChange={(e) => setActivityFilter(e.target.value)}
          />
        </Field>
      </div>

      {isLoading ? (
        <p>Loading…</p>
      ) : !entries?.length ? (
        <EmptyState title="No progress recorded yet" hint="Record progress here, or from a diary entry, to keep the schedule current." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Recorded</Th>
                <Th>Activity</Th>
                <Th>Measurement</Th>
                <Th>Value</Th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e: any) => (
                <tr key={e.id}>
                  <Td mono>{e.recorded_at ? new Date(e.recorded_at).toLocaleString() : "—"}</Td>
                  <Td mono>{e.activity_id.slice(0, 8)}…</Td>
                  <Td>{e.measurement_type}</Td>
                  <Td mono>
                    {e.value}
                    {e.unit ? ` ${e.unit}` : e.measurement_type === "percentage" ? "%" : ""}
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
