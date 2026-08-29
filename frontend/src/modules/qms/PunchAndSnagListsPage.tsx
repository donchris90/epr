import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, ErrorBanner, Field, Input } from "../../components/ui";
import { ProjectSelect } from "../../components/ProjectSelect";
import { getErrorMessage } from "../../api/client";
import {
  usePunchListItems,
  useCreatePunchListItem,
  useClosePunchListItem,
  useSnagListItems,
  useCreateSnagListItem,
  useCloseSnagListItem,
} from "./hooks";

function statusTone(status: string): "green" | "amber" {
  return status === "closed" ? "green" : "amber";
}

/** Real punch list and snag list items, backed by the real GET/POST
 * endpoints added while closing this batch's own frontend-backend
 * gap audit. Deliberately kept as two separate sections, not merged
 * -- SnagListItem is a real, deliberately separate table from
 * PunchListItem in the backend (see that model's own docstring),
 * and this page reflects that same real distinction rather than
 * flattening it away. */
export default function PunchAndSnagListsPage() {
  return (
    <div>
      <PageHeader eyebrow="Quality Management" title="Punch & Snag Lists" />
      <div style={{ display: "grid", gap: 24 }}>
        <PunchListSection />
        <SnagListSection />
      </div>
    </div>
  );
}

function PunchListSection() {
  const { data: items } = usePunchListItems();
  const createItem = useCreatePunchListItem();
  const closeItem = useClosePunchListItem();
  const [form, setForm] = useState({ project_id: "", area_building_section: "", description: "" });
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createItem.mutateAsync(form);
      setForm({ project_id: "", area_building_section: "", description: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Punch list</h3>
      <Card style={{ marginBottom: 16 }}>
        <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1.5fr auto", gap: 8 }}>
          <Field label="Project"><ProjectSelect required value={form.project_id} onChange={(v) => setForm({ ...form, project_id: v })} /></Field>
          <Field label="Area / building / section"><Input value={form.area_building_section} onChange={(e) => setForm({ ...form, area_building_section: e.target.value })} /></Field>
          <Field label="Description"><Input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Button type="submit" disabled={createItem.isPending} style={{ height: 38, alignSelf: "end" }}>
            {createItem.isPending ? "Adding…" : "Add"}
          </Button>
        </form>
        {error && <div style={{ marginTop: 12 }}><ErrorBanner title="Could not add item" detail={error} onDismiss={() => setError(null)} /></div>}
      </Card>
      <Card style={{ padding: 0 }}>
        {!items?.length ? (
          <EmptyState compact title="No punch list items yet." />
        ) : (
          <Table>
            <thead><tr><Th>Area</Th><Th>Description</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id}>
                  <Td>{i.area_building_section || "—"}</Td>
                  <Td>{i.description}</Td>
                  <Td><Badge tone={statusTone(i.status)}>{i.status}</Badge></Td>
                  <Td style={{ textAlign: "right" }}>
                    {i.status !== "closed" && (
                      <button onClick={() => closeItem.mutate(i.id)} style={{ background: "none", border: "none", color: "var(--sf-green)", cursor: "pointer" }}>Close</button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function SnagListSection() {
  const { data: items } = useSnagListItems();
  const createItem = useCreateSnagListItem();
  const closeItem = useCloseSnagListItem();
  const [form, setForm] = useState({ project_id: "", area_building_section: "", description: "" });
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createItem.mutateAsync(form);
      setForm({ project_id: "", area_building_section: "", description: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Snag list</h3>
      <Card style={{ marginBottom: 16 }}>
        <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1.5fr auto", gap: 8 }}>
          <Field label="Project"><ProjectSelect required value={form.project_id} onChange={(v) => setForm({ ...form, project_id: v })} /></Field>
          <Field label="Area / building / section"><Input value={form.area_building_section} onChange={(e) => setForm({ ...form, area_building_section: e.target.value })} /></Field>
          <Field label="Description"><Input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Button type="submit" disabled={createItem.isPending} style={{ height: 38, alignSelf: "end" }}>
            {createItem.isPending ? "Adding…" : "Add"}
          </Button>
        </form>
        {error && <div style={{ marginTop: 12 }}><ErrorBanner title="Could not add item" detail={error} onDismiss={() => setError(null)} /></div>}
      </Card>
      <Card style={{ padding: 0 }}>
        {!items?.length ? (
          <EmptyState compact title="No snag list items yet." />
        ) : (
          <Table>
            <thead><tr><Th>Area</Th><Th>Description</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id}>
                  <Td>{i.area_building_section || "—"}</Td>
                  <Td>{i.description}</Td>
                  <Td><Badge tone={statusTone(i.status)}>{i.status}</Badge></Td>
                  <Td style={{ textAlign: "right" }}>
                    {i.status !== "closed" && (
                      <button onClick={() => closeItem.mutate(i.id)} style={{ background: "none", border: "none", color: "var(--sf-green)", cursor: "pointer" }}>Close</button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
