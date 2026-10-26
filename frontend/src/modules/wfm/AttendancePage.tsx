import { useEffect, useMemo, useState } from "react";
import { PageHeader, Card, Button, Input, Select, Table, Th, Td, Badge, ErrorBanner, EmptyState } from "../../components/ui";
import { ProjectSelect } from "../../components/ProjectSelect";
import { getErrorMessage } from "../../api/client";
import { useAttendance, useBulkAttendance, useCasualWorkers, useEmployees, type BulkAttendanceResult } from "./hooks";
import { buildBulkRows, validateEntries, type CrewEntry, type Mark } from "./bulkAttendance";

const today = () => new Date().toISOString().slice(0, 10);

/** Record a whole crew's attendance for one project and day in one
 * go (POST /v1/wfm/attendance/bulk). People who already have a record
 * for that day are shown as recorded and left alone. */
export default function AttendancePage() {
  const [projectId, setProjectId] = useState("");
  const [date, setDate] = useState(today());
  const [assignedOnly, setAssignedOnly] = useState(true);
  const [defaults, setDefaults] = useState({ timeIn: "07:00", timeOut: "16:00" });
  type Edit = Partial<Pick<CrewEntry, "mark" | "timeIn" | "timeOut">>;
  const [marks, setMarks] = useState<Record<string, Edit>>({});
  const [outcome, setOutcome] = useState<BulkAttendanceResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const employees = useEmployees();
  const casuals = useCasualWorkers();
  const existing = useAttendance({ projectId: projectId || undefined, date });
  const bulk = useBulkAttendance();

  useEffect(() => {
    setMarks({});
    setOutcome(null);
  }, [projectId, date]);

  const recordedKeys = useMemo(
    () =>
      new Set(
        (existing.data ?? []).map((r: any) => (r.employee_id ? `e:${r.employee_id}` : `c:${r.casual_worker_id}`))
      ),
    [existing.data]
  );

  const entries: CrewEntry[] = useMemo(() => {
    const list: CrewEntry[] = [];
    for (const e of employees.data ?? []) {
      if (e.status !== "active") continue;
      if (assignedOnly && projectId && !(e.assigned_project_ids ?? []).includes(projectId)) continue;
      list.push({ key: `e:${e.id}`, kind: "employee", id: e.id, name: e.name, mark: "", timeIn: defaults.timeIn, timeOut: defaults.timeOut });
    }
    for (const c of casuals.data ?? []) {
      if (c.status !== "active") continue;
      list.push({ key: `c:${c.id}`, kind: "casual", id: c.id, name: c.name, mark: "", timeIn: defaults.timeIn, timeOut: defaults.timeOut });
    }
    return list.map((e) => ({ ...e, ...(marks[e.key] ?? {}) }));
  }, [employees.data, casuals.data, assignedOnly, projectId, defaults, marks]);

  const open = entries.filter((e) => !recordedKeys.has(e.key));

  function update(key: string, patch: Edit) {
    setMarks((m) => ({ ...m, [key]: { ...m[key], ...patch } }));
  }

  function markAllPresent() {
    setMarks((m) => {
      const next = { ...m };
      for (const e of open) next[e.key] = { ...m[e.key], mark: "present" };
      return next;
    });
  }

  async function save() {
    setError(null);
    setOutcome(null);
    const problem = validateEntries(open);
    if (problem) {
      setError(problem);
      return;
    }
    try {
      const result = await bulk.mutateAsync({ project_id: projectId, attendance_date: date, rows: buildBulkRows(open, date) });
      setOutcome(result);
      setMarks({});
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  const failed = outcome?.results.filter((r) => r.status === "error") ?? [];
  const markedCount = open.filter((e) => e.mark !== "").length;

  return (
    <div>
      <PageHeader eyebrow="Workforce" title="Daily Attendance" />
      <Card style={{ marginBottom: 16 }}>
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 12, alignItems: "end" }}>
          <label style={{ fontSize: 12 }}>
            Project
            <ProjectSelect value={projectId} onChange={setProjectId} />
          </label>
          <label style={{ fontSize: 12 }}>
            Date
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Attendance date" />
          </label>
          <label style={{ fontSize: 12 }}>
            Usual start
            <Input type="time" value={defaults.timeIn} onChange={(e) => setDefaults({ ...defaults, timeIn: e.target.value })} />
          </label>
          <label style={{ fontSize: 12 }}>
            Usual finish
            <Input type="time" value={defaults.timeOut} onChange={(e) => setDefaults({ ...defaults, timeOut: e.target.value })} />
          </label>
        </div>
        <label style={{ fontSize: 12, display: "block", marginTop: 10 }}>
          <input type="checkbox" checked={assignedOnly} onChange={(e) => setAssignedOnly(e.target.checked)} /> Only employees assigned to this project (casual workers always shown)
        </label>
      </Card>

      {error && <ErrorBanner title={error} />}
      {outcome && (
        <Card style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13 }}>
            Saved {outcome.created}
            {outcome.skipped ? `, ${outcome.skipped} already recorded` : ""}
            {outcome.error ? `, ${outcome.error} failed` : ""}.
          </div>
          {failed.map((f) => (
            <div key={f.index} style={{ fontSize: 12, color: "var(--sf-brick)" }}>
              Row {f.index + 1}: {f.error}
            </div>
          ))}
        </Card>
      )}

      {!projectId ? (
        <EmptyState title="Choose a project" hint="Pick the project and day to record attendance for." />
      ) : entries.length === 0 ? (
        <EmptyState title="No workers to record" hint="No active employees are assigned to this project and there are no active casual workers." />
      ) : (
        <>
          <div style={{ marginBottom: 8 }}>
            <Button variant="secondary" onClick={markAllPresent}>Mark all present</Button>
          </div>
          <Table ariaLabel="Crew attendance">
            <thead>
              <tr><Th>Name</Th><Th>Type</Th><Th>Attendance</Th><Th>Start</Th><Th>Finish</Th></tr>
            </thead>
            <tbody>
              {entries.map((e) => {
                const recorded = recordedKeys.has(e.key);
                return (
                  <tr key={e.key}>
                    <Td>{e.name}</Td>
                    <Td>{e.kind === "employee" ? "Employee" : "Casual"}</Td>
                    <Td>
                      {recorded ? (
                        <Badge tone="green">Recorded</Badge>
                      ) : (
                        <Select aria-label={`Attendance for ${e.name}`} value={e.mark} onChange={(ev) => update(e.key, { mark: ev.target.value as Mark })}>
                          <option value="">—</option>
                          <option value="present">Present</option>
                          <option value="absent">Absent</option>
                        </Select>
                      )}
                    </Td>
                    <Td>{!recorded && e.mark === "present" && <Input type="time" aria-label={`Start for ${e.name}`} value={e.timeIn} onChange={(ev) => update(e.key, { timeIn: ev.target.value })} />}</Td>
                    <Td>{!recorded && e.mark === "present" && <Input type="time" aria-label={`Finish for ${e.name}`} value={e.timeOut} onChange={(ev) => update(e.key, { timeOut: ev.target.value })} />}</Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
          <div style={{ marginTop: 12 }}>
            <Button onClick={save} disabled={bulk.isPending || markedCount === 0}>
              {bulk.isPending ? "Saving…" : `Save attendance (${markedCount})`}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
