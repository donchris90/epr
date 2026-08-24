import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, ErrorBanner, Input, Field, Select, formatMoney } from "../../components/ui";
import { ProjectSelect } from "../../components/ProjectSelect";
import {
  useEmployee,
  useUpdateEmployee,
  useTerminateEmployee,
  useReactivateEmployee,
  useAssignProject,
  useTransferProject,
  useAttendance,
  useMarkAbsent,
  useCorrectAttendance,
  useTimesheets,
  useLeaveRequests,
  useCreateLeaveRequest,
  useCancelLeaveRequest,
  useLeaveBalance,
  useAddTrainingRecord,
  useAddCompetency,
  useAddCertification,
} from "./hooks";
import { getErrorMessage } from "../../api/client";

const TABS = [
  "Overview",
  "Employment",
  "Project Assignments",
  "Attendance",
  "Timesheets",
  "Leave",
  "Training",
  "Certifications",
  "Competencies",
] as const;
type Tab = (typeof TABS)[number];

function statusTone(status: string): "green" | "neutral" | "brick" | "amber" {
  if (status === "active" || status === "approved") return "green";
  if (status === "inactive" || status === "rejected" || status === "cancelled") return "brick";
  if (status === "pending" || status === "pending_approval") return "amber";
  return "neutral";
}

/** Real employee detail hub, backed entirely by real backend
 * endpoints added this batch (GET/PUT /wfm/employees/<id>, terminate/
 * reactivate/assign-project/transfer-project, and every real list
 * endpoint each tab below reads from). No Payroll, Documents, or
 * History tab: Payroll is period-scoped, not naturally per-employee
 * (a real payroll run's own detail page is the right home for that,
 * not duplicated here); Documents has no real wfm-specific document
 * link in this backend; History has no real audit-log endpoint to
 * read from. See docs/WFM_SUB_GAPS.md. */
export default function EmployeeDetailPage() {
  const { employeeId } = useParams<{ employeeId: string }>();
  const { data: employee, isLoading, error } = useEmployee(employeeId);
  const [tab, setTab] = useState<Tab>("Overview");

  if (isLoading) return <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>;
  if (error || !employee) return <ErrorBanner title="Could not load employee" detail={getErrorMessage(error)} />;

  return (
    <div>
      <PageHeader
        eyebrow="Workforce Management"
        title={employee.name}
        action={<Badge tone={statusTone(employee.status)}>{employee.status}</Badge>}
      />
      <div style={{ display: "flex", gap: 4, marginBottom: 20, flexWrap: "wrap", borderBottom: "1px solid var(--sf-line)" }}>
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "8px 12px",
              fontSize: 12,
              fontWeight: 600,
              background: "none",
              border: "none",
              cursor: "pointer",
              color: tab === t ? "var(--sf-navy-900)" : "var(--sf-navy-400)",
              borderBottom: tab === t ? "2px solid var(--sf-amber)" : "2px solid transparent",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Overview" && <OverviewTab employee={employee} />}
      {tab === "Employment" && <EmploymentTab employee={employee} />}
      {tab === "Project Assignments" && <ProjectAssignmentsTab employee={employee} />}
      {tab === "Attendance" && <AttendanceTab employee={employee} />}
      {tab === "Timesheets" && <TimesheetsTab employee={employee} />}
      {tab === "Leave" && <LeaveTab employee={employee} />}
      {tab === "Training" && <TrainingTab employee={employee} />}
      {tab === "Certifications" && <CertificationsTab employee={employee} />}
      {tab === "Competencies" && <CompetenciesTab employee={employee} />}
    </div>
  );
}

function OverviewTab({ employee }: { employee: import("./hooks").Employee }) {
  const terminate = useTerminateEmployee(employee.id);
  const reactivate = useReactivateEmployee(employee.id);
  const [error, setError] = useState<string | null>(null);

  async function handleTerminate() {
    if (!confirm(`Terminate ${employee.name}? This will mark them inactive.`)) return;
    try {
      await terminate.mutateAsync();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Overview</h3>
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: 13 }}>
          <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Role</div>{employee.role || "—"}</div>
          <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Trade</div>{employee.trade || "—"}</div>
          <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Employment type</div>{employee.employment_type}</div>
          <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Pay grade</div>{employee.pay_grade || "—"}</div>
          <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Employee number</div>{employee.employee_number || "—"}</div>
          <div><div style={{ color: "var(--sf-navy-400)", fontSize: 11 }}>Assigned projects</div>{employee.assigned_project_ids?.length ?? 0}</div>
        </div>
      </Card>
      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Actions</h3>
        {error && <ErrorBanner title="Action failed" detail={error} onDismiss={() => setError(null)} />}
        {employee.status === "active" ? (
          <Button variant="secondary" onClick={handleTerminate} disabled={terminate.isPending}>
            {terminate.isPending ? "Terminating…" : "Terminate"}
          </Button>
        ) : (
          <Button onClick={() => reactivate.mutate()} disabled={reactivate.isPending}>
            {reactivate.isPending ? "Reactivating…" : "Reactivate"}
          </Button>
        )}
      </Card>
    </div>
  );
}

function EmploymentTab({ employee }: { employee: import("./hooks").Employee }) {
  const update = useUpdateEmployee(employee.id);
  const [form, setForm] = useState({
    role: employee.role ?? "",
    trade: employee.trade ?? "",
    pay_grade: employee.pay_grade ?? "",
    monthly_rate: employee.monthly_rate ?? "",
  });
  const [saved, setSaved] = useState(false);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaved(false);
    await update.mutateAsync(form);
    setSaved(true);
  }

  return (
    <Card style={{ maxWidth: 480 }}>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Employment details</h3>
      <form onSubmit={handleSave}>
        <Field label="Role"><Input value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} /></Field>
        <Field label="Trade"><Input value={form.trade} onChange={(e) => setForm({ ...form, trade: e.target.value })} /></Field>
        <Field label="Pay grade"><Input value={form.pay_grade} onChange={(e) => setForm({ ...form, pay_grade: e.target.value })} /></Field>
        <Field label="Monthly rate"><Input type="number" step="0.01" value={form.monthly_rate} onChange={(e) => setForm({ ...form, monthly_rate: e.target.value })} /></Field>
        {saved && <div style={{ color: "var(--sf-green)", fontSize: 12, marginBottom: 10 }}>Saved.</div>}
        <Button type="submit" disabled={update.isPending}>{update.isPending ? "Saving…" : "Save"}</Button>
      </form>
    </Card>
  );
}

function ProjectAssignmentsTab({ employee }: { employee: import("./hooks").Employee }) {
  const assign = useAssignProject(employee.id);
  const transfer = useTransferProject(employee.id);
  const [newProject, setNewProject] = useState("");
  const [transferFrom, setTransferFrom] = useState("");
  const [transferTo, setTransferTo] = useState("");

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Currently assigned</h3>
        {employee.assigned_project_ids?.length ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            {employee.assigned_project_ids.map((pid) => <li key={pid} className="sf-mono">{pid}</li>)}
          </ul>
        ) : (
          <EmptyState compact title="No project assignments yet." />
        )}
      </Card>
      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Assign a project</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <ProjectSelect value={newProject} onChange={setNewProject} />
          <Button onClick={() => assign.mutate(newProject)} disabled={!newProject || assign.isPending}>Assign</Button>
        </div>
      </Card>
      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Transfer to another project</h3>
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8 }}>
          <ProjectSelect value={transferFrom} onChange={setTransferFrom} placeholder="From project" />
          <ProjectSelect value={transferTo} onChange={setTransferTo} placeholder="To project" />
          <Button
            onClick={() => transfer.mutate({ from_project_id: transferFrom, to_project_id: transferTo })}
            disabled={!transferFrom || !transferTo || transfer.isPending}
          >
            Transfer
          </Button>
        </div>
      </Card>
    </div>
  );
}

function AttendanceTab({ employee }: { employee: import("./hooks").Employee }) {
  const { data: records } = useAttendance({ employeeId: employee.id });
  const markAbsent = useMarkAbsent();
  const correctAttendance = useCorrectAttendance();
  const [form, setForm] = useState({ project_id: "", attendance_date: new Date().toISOString().slice(0, 10) });
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ check_in_at: "", check_out_at: "" });

  async function handleMarkAbsent() {
    setError(null);
    try {
      await markAbsent.mutateAsync({ ...form, employee_id: employee.id });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  function startEdit(recordId: string, checkIn: string | null, checkOut: string | null) {
    setEditingId(recordId);
    setEditForm({
      check_in_at: checkIn ? checkIn.slice(0, 16) : "",
      check_out_at: checkOut ? checkOut.slice(0, 16) : "",
    });
  }

  async function handleSaveCorrection(recordId: string) {
    setError(null);
    try {
      await correctAttendance.mutateAsync({
        recordId,
        check_in_at: editForm.check_in_at || undefined,
        check_out_at: editForm.check_out_at || undefined,
      });
      setEditingId(null);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Mark absent</h3>
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8 }}>
          <ProjectSelect value={form.project_id} onChange={(project_id) => setForm({ ...form, project_id })} />
          <Input type="date" value={form.attendance_date} onChange={(e) => setForm({ ...form, attendance_date: e.target.value })} />
          <Button onClick={handleMarkAbsent} disabled={!form.project_id || markAbsent.isPending}>Mark absent</Button>
        </div>
        {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginTop: 8 }}>{error}</div>}
      </Card>
      <Card style={{ padding: 0 }}>
        {!records?.length ? (
          <EmptyState compact title="No attendance records yet." />
        ) : (
          <Table>
            <thead><tr><Th>Date</Th><Th>Check in</Th><Th>Check out</Th><Th>Method</Th><Th /></tr></thead>
            <tbody>
              {records.map((r) =>
                editingId === r.id ? (
                  <tr key={r.id}>
                    <Td mono>{r.attendance_date}</Td>
                    <Td><Input type="datetime-local" value={editForm.check_in_at} onChange={(e) => setEditForm({ ...editForm, check_in_at: e.target.value })} /></Td>
                    <Td><Input type="datetime-local" value={editForm.check_out_at} onChange={(e) => setEditForm({ ...editForm, check_out_at: e.target.value })} /></Td>
                    <Td>{r.capture_method}</Td>
                    <Td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      <button onClick={() => handleSaveCorrection(r.id)} disabled={correctAttendance.isPending} style={{ background: "none", border: "none", color: "var(--sf-green)", cursor: "pointer", marginRight: 8 }}>
                        Save
                      </button>
                      <button onClick={() => setEditingId(null)} style={{ background: "none", border: "none", color: "var(--sf-navy-400)", cursor: "pointer" }}>
                        Cancel
                      </button>
                    </Td>
                  </tr>
                ) : (
                  <tr key={r.id}>
                    <Td mono>{r.attendance_date}</Td>
                    <Td mono>{r.check_in_at ? new Date(r.check_in_at).toLocaleTimeString() : "—"}</Td>
                    <Td mono>{r.check_out_at ? new Date(r.check_out_at).toLocaleTimeString() : "—"}</Td>
                    <Td>{r.capture_method}</Td>
                    <Td style={{ textAlign: "right" }}>
                      <button onClick={() => startEdit(r.id, r.check_in_at, r.check_out_at)} style={{ background: "none", border: "none", color: "var(--sf-steel)", cursor: "pointer" }}>
                        Correct
                      </button>
                    </Td>
                  </tr>
                )
              )}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function TimesheetsTab({ employee }: { employee: import("./hooks").Employee }) {
  const { data: timesheets } = useTimesheets();
  const own = timesheets?.filter((t) => t.employee_id === employee.id) ?? [];

  return (
    <Card style={{ padding: 0 }}>
      {!own.length ? (
        <EmptyState compact title="No timesheets yet." />
      ) : (
        <Table>
          <thead><tr><Th>Period</Th><Th>Hours</Th><Th>Rate</Th><Th>Gross</Th><Th>Status</Th></tr></thead>
          <tbody>
            {own.map((t) => (
              <tr key={t.id}>
                <Td mono>{t.period_start} – {t.period_end}</Td>
                <Td mono>{t.hours_or_units}</Td>
                <Td mono>{formatMoney(t.rate_applied)}</Td>
                <Td mono>{formatMoney(t.gross_amount)}</Td>
                <Td><Badge tone={statusTone(t.status)}>{t.status}</Badge></Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

const LEAVE_TYPES = ["annual", "sick", "compassionate", "maternity", "paternity", "unpaid"];

function LeaveTab({ employee }: { employee: import("./hooks").Employee }) {
  const { data: leaves } = useLeaveRequests({ employeeId: employee.id });
  const { data: balance } = useLeaveBalance(employee.id);
  const createLeave = useCreateLeaveRequest();
  const cancelLeave = useCancelLeaveRequest();
  const [form, setForm] = useState({ leave_type: "annual", start_date: "", end_date: "", reason: "" });

  async function handleRequest(e: React.FormEvent) {
    e.preventDefault();
    await createLeave.mutateAsync({ employee_id: employee.id, ...form });
    setForm({ leave_type: "annual", start_date: "", end_date: "", reason: "" });
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 8 }}>Days taken this year</h3>
        {balance && Object.keys(balance).length ? (
          <div style={{ display: "flex", gap: 16 }}>
            {Object.entries(balance).map(([type, days]) => (
              <div key={type}>
                <div className="sf-mono" style={{ fontSize: 18, fontWeight: 700 }}>{days}</div>
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>{type}</div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState compact title="No approved leave taken this year." />
        )}
      </Card>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Request leave</h3>
        <form onSubmit={handleRequest} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 8 }}>
          <Select value={form.leave_type} onChange={(e) => setForm({ ...form, leave_type: e.target.value })}>
            {LEAVE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </Select>
          <Input type="date" required value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          <Input type="date" required value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
          <Button type="submit" disabled={createLeave.isPending}>Request</Button>
        </form>
      </Card>

      <Card style={{ padding: 0 }}>
        {!leaves?.length ? (
          <EmptyState compact title="No leave requests yet." />
        ) : (
          <Table>
            <thead><tr><Th>Type</Th><Th>From</Th><Th>To</Th><Th>Status</Th><Th /></tr></thead>
            <tbody>
              {leaves.map((l) => (
                <tr key={l.id}>
                  <Td>{l.leave_type}</Td>
                  <Td mono>{l.start_date}</Td>
                  <Td mono>{l.end_date}</Td>
                  <Td><Badge tone={statusTone(l.status)}>{l.status}</Badge></Td>
                  <Td style={{ textAlign: "right" }}>
                    {(l.status === "pending" || l.status === "approved") && (
                      <button
                        onClick={() => cancelLeave.mutate(l.id)}
                        style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, cursor: "pointer" }}
                      >
                        Cancel
                      </button>
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

function TrainingTab({ employee }: { employee: import("./hooks").Employee }) {
  const addTraining = useAddTrainingRecord(employee.id);
  const [form, setForm] = useState({ course_name: "", provider: "", completion_date: "", expiry_date: "" });

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    await addTraining.mutateAsync(form);
    setForm({ course_name: "", provider: "", completion_date: "", expiry_date: "" });
  }

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Add training record</h3>
      <form onSubmit={handleAdd} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr auto", gap: 8 }}>
        <Input required placeholder="Course name" value={form.course_name} onChange={(e) => setForm({ ...form, course_name: e.target.value })} />
        <Input placeholder="Provider" value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} />
        <Input type="date" placeholder="Completion date" value={form.completion_date} onChange={(e) => setForm({ ...form, completion_date: e.target.value })} />
        <Input type="date" placeholder="Expiry date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} />
        <Button type="submit" disabled={addTraining.isPending}>Add</Button>
      </form>
    </Card>
  );
}

function CertificationsTab({ employee }: { employee: import("./hooks").Employee }) {
  const addCert = useAddCertification(employee.id);
  const [form, setForm] = useState({ certification_type: "", certificate_number: "", issuing_body: "", expiry_date: "" });

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    await addCert.mutateAsync(form);
    setForm({ certification_type: "", certificate_number: "", issuing_body: "", expiry_date: "" });
  }

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Add certification</h3>
      <form onSubmit={handleAdd} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr auto", gap: 8 }}>
        <Input required placeholder="Certification type" value={form.certification_type} onChange={(e) => setForm({ ...form, certification_type: e.target.value })} />
        <Input placeholder="Certificate number" value={form.certificate_number} onChange={(e) => setForm({ ...form, certificate_number: e.target.value })} />
        <Input placeholder="Issuing body" value={form.issuing_body} onChange={(e) => setForm({ ...form, issuing_body: e.target.value })} />
        <Input type="date" placeholder="Expiry date" value={form.expiry_date} onChange={(e) => setForm({ ...form, expiry_date: e.target.value })} />
        <Button type="submit" disabled={addCert.isPending}>Add</Button>
      </form>
    </Card>
  );
}

function CompetenciesTab({ employee }: { employee: import("./hooks").Employee }) {
  const addCompetency = useAddCompetency(employee.id);
  const [form, setForm] = useState({ skill_or_equipment_type: "", proficiency_level: "" });

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    await addCompetency.mutateAsync(form);
    setForm({ skill_or_equipment_type: "", proficiency_level: "" });
  }

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 12 }}>Add competency</h3>
      <form onSubmit={handleAdd} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 8 }}>
        <Input required placeholder="Skill or equipment type" value={form.skill_or_equipment_type} onChange={(e) => setForm({ ...form, skill_or_equipment_type: e.target.value })} />
        <Input placeholder="Proficiency level" value={form.proficiency_level} onChange={(e) => setForm({ ...form, proficiency_level: e.target.value })} />
        <Button type="submit" disabled={addCompetency.isPending}>Add</Button>
      </form>
    </Card>
  );
}
