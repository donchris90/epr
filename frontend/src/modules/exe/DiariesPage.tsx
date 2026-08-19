import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { ProjectSelect } from "../../components/ProjectSelect";
import { useDiaries, useCreateDiary } from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green"> = {
  draft: "neutral",
  signed: "amber",
  countersigned: "green",
};

export default function DiariesPage() {
  const [projectId, setProjectId] = useState("");
  const { data: diaries, isLoading } = useDiaries(projectId || undefined);
  const createDiary = useCreateDiary();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ project_id: "", diary_date: "", workforce_present_count: "", narrative: "" });

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createDiary.mutateAsync({
      project_id: form.project_id,
      diary_date: form.diary_date,
      workforce_present_count: form.workforce_present_count ? Number(form.workforce_present_count) : undefined,
      narrative: form.narrative || undefined,
    });
    setForm({ project_id: "", diary_date: "", workforce_present_count: "", narrative: "" });
    setShowForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Project Execution"
        title="Daily Site Diaries"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New diary entry"}</Button>}
      />

      <div style={{ marginBottom: 20, maxWidth: 320 }}>
        <Field label="Filter by project">
          <ProjectSelect value={projectId} onChange={setProjectId} />
        </Field>
      </div>

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 16 }}>
              <Field label="Project">
                <ProjectSelect
                  required
                  value={form.project_id}
                  onChange={(projectId) => setForm({ ...form, project_id: projectId })}
                  includeEmptyOption={!form.project_id}
                />
              </Field>
              <Field label="Diary date">
                <Input
                  required
                  type="date"
                  value={form.diary_date}
                  onChange={(e) => setForm({ ...form, diary_date: e.target.value })}
                />
              </Field>
              <Field label="Workforce present">
                <Input
                  type="number"
                  min={0}
                  value={form.workforce_present_count}
                  onChange={(e) => setForm({ ...form, workforce_present_count: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Narrative (optional)">
              <textarea
                value={form.narrative}
                onChange={(e) => setForm({ ...form, narrative: e.target.value })}
                placeholder="Summary of today's activity on site…"
                rows={3}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  border: "1px solid var(--sf-line)",
                  borderRadius: "var(--sf-radius)",
                  fontSize: 13,
                  fontFamily: "inherit",
                  resize: "vertical",
                }}
              />
            </Field>
            <Button type="submit" disabled={createDiary.isPending}>
              {createDiary.isPending ? "Saving…" : "Create diary entry"}
            </Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !diaries?.length ? (
        <EmptyState
          title="No diary entries yet"
          hint="A signed diary is the daily record of record for a project — start one for today's activity."
        />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Date</Th>
                <Th>Workforce</Th>
                <Th>Status</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {diaries.map((d: any) => (
                <tr key={d.id}>
                  <Td mono>{new Date(d.diary_date).toLocaleDateString()}</Td>
                  <Td mono>{d.workforce_present_count ?? "—"}</Td>
                  <Td>
                    <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>{d.status}</Badge>
                  </Td>
                  <Td>
                    <Link to={`diaries/${d.id}`} style={{ fontSize: 12, fontWeight: 600 }}>
                      Open →
                    </Link>
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
