import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { ProjectSelect } from "../../components/ProjectSelect";
import {
  useWBSNodes,
  useCreateWBSNode,
  useProjectActivities,
  useAddActivity,
  useAddDependency,
  useRecalculateSchedule,
} from "./hooks";

export default function SchedulePage() {
  const [projectId, setProjectId] = useState("");
  const { data: wbsNodes } = useWBSNodes(projectId || undefined);
  const { data: activities, isLoading: activitiesLoading } = useProjectActivities(projectId || undefined);
  const createWBSNode = useCreateWBSNode();
  const recalculate = useRecalculateSchedule();

  const [showNodeForm, setShowNodeForm] = useState(false);
  const [nodeForm, setNodeForm] = useState({ code: "", name: "" });
  const [activityWbsNodeId, setActivityWbsNodeId] = useState("");
  const [activityForm, setActivityForm] = useState({ name: "", planned_start: "", duration_days: "" });
  const addActivity = useAddActivity(activityWbsNodeId || undefined);

  const [depForm, setDepForm] = useState({ predecessor_id: "", successor_id: "", dependency_type: "FS", lag_days: "0" });
  const addDependency = useAddDependency();

  const nodesById: Record<string, any> = Object.fromEntries((wbsNodes ?? []).map((n: any) => [n.id, n]));

  async function handleCreateNode(e: React.FormEvent) {
    e.preventDefault();
    await createWBSNode.mutateAsync({ project_id: projectId, code: nodeForm.code || undefined, name: nodeForm.name });
    setNodeForm({ code: "", name: "" });
    setShowNodeForm(false);
  }

  async function handleAddActivity(e: React.FormEvent) {
    e.preventDefault();
    if (!activityWbsNodeId) return;
    await addActivity.mutateAsync({
      name: activityForm.name,
      planned_start: activityForm.planned_start,
      duration_days: Number(activityForm.duration_days),
    });
    setActivityForm({ name: "", planned_start: "", duration_days: "" });
  }

  async function handleAddDependency(e: React.FormEvent) {
    e.preventDefault();
    await addDependency.mutateAsync({
      predecessor_id: depForm.predecessor_id,
      successor_id: depForm.successor_id,
      dependency_type: depForm.dependency_type,
      lag_days: Number(depForm.lag_days) || 0,
    });
    setDepForm({ predecessor_id: "", successor_id: "", dependency_type: "FS", lag_days: "0" });
  }

  async function handleRecalculate() {
    // Recalculation runs per WBS root; trigger it for every root node
    // under this project so the whole schedule reflects the latest
    // activities and dependencies.
    const roots = (wbsNodes ?? []).filter((n: any) => !n.parent_id);
    for (const root of roots) {
      await recalculate.mutateAsync(root.id);
    }
  }

  return (
    <div>
      <PageHeader eyebrow="Project Planning" title="Schedule" />

      <div style={{ marginBottom: 20, maxWidth: 320 }}>
        <Field label="Project ID">
          <ProjectSelect value={projectId} onChange={setProjectId} />
        </Field>
      </div>

      {projectId && (
        <>
          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            <Button variant="secondary" onClick={() => setShowNodeForm((v) => !v)}>
              {showNodeForm ? "Cancel" : "New WBS node"}
            </Button>
            <Button onClick={handleRecalculate} disabled={recalculate.isPending || !wbsNodes?.length}>
              {recalculate.isPending ? "Recalculating…" : "Recalculate schedule (CPM)"}
            </Button>
          </div>

          {showNodeForm && (
            <Card style={{ marginBottom: 20 }}>
              <form onSubmit={handleCreateNode} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 3fr auto", gap: 12 }}>
                <Field label="Code">
                  <Input placeholder="1.0" value={nodeForm.code} onChange={(e) => setNodeForm({ ...nodeForm, code: e.target.value })} />
                </Field>
                <Field label="Name">
                  <Input
                    required
                    placeholder="e.g. Foundations"
                    value={nodeForm.name}
                    onChange={(e) => setNodeForm({ ...nodeForm, name: e.target.value })}
                  />
                </Field>
                <Button type="submit" disabled={createWBSNode.isPending} style={{ height: 38, alignSelf: "end" }}>
                  Add
                </Button>
              </form>
            </Card>
          )}

          {wbsNodes?.length ? (
            <Card style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Add an activity</h3>
              <form onSubmit={handleAddActivity} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 2fr 1fr 1fr auto", gap: 12 }}>
                <Field label="WBS node">
                  <select
                    required
                    value={activityWbsNodeId}
                    onChange={(e) => setActivityWbsNodeId(e.target.value)}
                    style={{
                      padding: "8px 10px",
                      border: "1px solid var(--sf-line)",
                      borderRadius: "var(--sf-radius)",
                      fontSize: 13,
                      width: "100%",
                      background: "#fff",
                    }}
                  >
                    <option value="">Select…</option>
                    {wbsNodes.map((n: any) => (
                      <option key={n.id} value={n.id}>
                        {n.code ? `${n.code} ` : ""}
                        {n.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Activity name">
                  <Input required value={activityForm.name} onChange={(e) => setActivityForm({ ...activityForm, name: e.target.value })} />
                </Field>
                <Field label="Planned start">
                  <Input
                    required
                    type="date"
                    value={activityForm.planned_start}
                    onChange={(e) => setActivityForm({ ...activityForm, planned_start: e.target.value })}
                  />
                </Field>
                <Field label="Duration (days)">
                  <Input
                    required
                    type="number"
                    min={1}
                    value={activityForm.duration_days}
                    onChange={(e) => setActivityForm({ ...activityForm, duration_days: e.target.value })}
                  />
                </Field>
                <Button type="submit" disabled={addActivity.isPending} style={{ height: 38, alignSelf: "end" }}>
                  Add
                </Button>
              </form>
            </Card>
          ) : (
            <EmptyState title="No WBS structure yet" hint="Add a WBS node to start building this project's schedule." />
          )}

          {activities?.length ? (
            <Card style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Link a dependency</h3>
              <form onSubmit={handleAddDependency} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr 1fr 1fr auto", gap: 12 }}>
                <Field label="Predecessor">
                  <select
                    required
                    value={depForm.predecessor_id}
                    onChange={(e) => setDepForm({ ...depForm, predecessor_id: e.target.value })}
                    style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, width: "100%", background: "#fff" }}
                  >
                    <option value="">Select…</option>
                    {activities.map((a: any) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Successor">
                  <select
                    required
                    value={depForm.successor_id}
                    onChange={(e) => setDepForm({ ...depForm, successor_id: e.target.value })}
                    style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, width: "100%", background: "#fff" }}
                  >
                    <option value="">Select…</option>
                    {activities.map((a: any) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Type">
                  <select
                    value={depForm.dependency_type}
                    onChange={(e) => setDepForm({ ...depForm, dependency_type: e.target.value })}
                    style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, width: "100%", background: "#fff" }}
                  >
                    <option value="FS">Finish-to-Start</option>
                    <option value="SS">Start-to-Start</option>
                    <option value="FF">Finish-to-Finish</option>
                    <option value="SF">Start-to-Finish</option>
                  </select>
                </Field>
                <Field label="Lag (days)">
                  <Input
                    type="number"
                    value={depForm.lag_days}
                    onChange={(e) => setDepForm({ ...depForm, lag_days: e.target.value })}
                  />
                </Field>
                <Button type="submit" disabled={addDependency.isPending} style={{ height: 38, alignSelf: "end" }}>
                  Link
                </Button>
              </form>
            </Card>
          ) : null}

          {activitiesLoading ? (
            <p>Loading…</p>
          ) : !activities?.length ? null : (
            <Card style={{ padding: 0 }}>
              <Table>
                <thead>
                  <tr>
                    <Th>WBS</Th>
                    <Th>Activity</Th>
                    <Th>Planned start</Th>
                    <Th>Duration</Th>
                    <Th>Early start</Th>
                    <Th>Early finish</Th>
                    <Th>Float</Th>
                    <Th></Th>
                  </tr>
                </thead>
                <tbody>
                  {activities.map((a: any) => (
                    <tr key={a.id} style={a.is_critical ? { background: "var(--sf-brick-dim)" } : undefined}>
                      <Td mono style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>
                        {nodesById[a.wbs_node_id]?.code || nodesById[a.wbs_node_id]?.name || "—"}
                      </Td>
                      <Td>{a.name}</Td>
                      <Td mono>{new Date(a.planned_start).toLocaleDateString()}</Td>
                      <Td mono>{a.duration_days}d</Td>
                      <Td mono>{a.early_start ? new Date(a.early_start).toLocaleDateString() : "—"}</Td>
                      <Td mono>{a.early_finish ? new Date(a.early_finish).toLocaleDateString() : "—"}</Td>
                      <Td mono>{a.total_float_days ?? "—"}</Td>
                      <Td>{a.is_critical && <Badge tone="brick">Critical path</Badge>}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          )}
        </>
      )}

      {!projectId && (
        <EmptyState title="Enter a project ID" hint="The schedule is built per project — paste a project UUID above to get started." />
      )}
    </div>
  );
}
