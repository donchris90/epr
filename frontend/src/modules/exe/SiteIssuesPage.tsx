import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, Select } from "../../components/ui";
import { useSiteIssues, useCreateSiteIssue, useEscalateOverdueIssues } from "./hooks";

const SEVERITY_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  low: "neutral",
  medium: "steel",
  high: "amber",
  critical: "brick",
};

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  open: "amber",
  in_progress: "steel",
  resolved: "green",
  escalated: "brick",
};

export default function SiteIssuesPage() {
  const [projectId, setProjectId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const { data: issues, isLoading } = useSiteIssues(projectId || undefined, statusFilter || undefined);
  const createIssue = useCreateSiteIssue();
  const escalate = useEscalateOverdueIssues();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ project_id: "", category: "", severity: "medium", description: "", due_date: "" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createIssue.mutateAsync({
      project_id: form.project_id,
      category: form.category || undefined,
      severity: form.severity,
      description: form.description,
      due_date: form.due_date || undefined,
    });
    setForm({ project_id: form.project_id, category: "", severity: "medium", description: "", due_date: "" });
    setShowForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Project Execution"
        title="Site Issues"
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" onClick={() => escalate.mutate()} disabled={escalate.isPending}>
              {escalate.isPending ? "Checking…" : "Escalate overdue"}
            </Button>
            <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "Log issue"}</Button>
          </div>
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20, maxWidth: 500 }}>
        <Field label="Filter by project ID">
          <Input placeholder="Project UUID" value={projectId} onChange={(e) => setProjectId(e.target.value)} />
        </Field>
        <Field label="Filter by status">
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In progress</option>
            <option value="resolved">Resolved</option>
            <option value="escalated">Escalated</option>
          </Select>
        </Field>
      </div>

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 16 }}>
              <Field label="Project ID">
                <Input
                  required
                  placeholder="Project UUID"
                  value={form.project_id}
                  onChange={(e) => setForm({ ...form, project_id: e.target.value })}
                />
              </Field>
              <Field label="Category (optional)">
                <Input
                  placeholder="e.g. Access, Design query"
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                />
              </Field>
              <Field label="Severity">
                <Select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </Select>
              </Field>
              <Field label="Due date (optional)">
                <Input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
              </Field>
            </div>
            <Field label="Description">
              <Input
                required
                placeholder="What's blocking or affecting the works?"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </Field>
            <Button type="submit" disabled={createIssue.isPending}>
              {createIssue.isPending ? "Logging…" : "Log issue"}
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !issues?.length ? (
        <EmptyState title="No site issues logged" hint="Nothing tracked here yet — issues raised on site will appear once logged." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Description</Th>
                <Th>Category</Th>
                <Th>Severity</Th>
                <Th>Status</Th>
                <Th>Due</Th>
              </tr>
            </thead>
            <tbody>
              {issues.map((i: any) => (
                <tr key={i.id}>
                  <Td>{i.description}</Td>
                  <Td>{i.category || "—"}</Td>
                  <Td>
                    <Badge tone={SEVERITY_TONE[i.severity] ?? "neutral"}>{i.severity}</Badge>
                  </Td>
                  <Td>
                    <Badge tone={STATUS_TONE[i.status] ?? "neutral"}>{i.status.replace(/_/g, " ")}</Badge>
                  </Td>
                  <Td mono>{i.due_date ? new Date(i.due_date).toLocaleDateString() : "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
