import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input } from "../../components/ui";
import { useTimesheets, useGenerateTimesheet, useDecideTimesheet, useLeaveRequests, useCreateLeaveRequest, useDecideLeaveRequest } from "./hooks";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  pending_approval: "amber",
  approved: "green",
  rejected: "brick",
};

export default function TimesheetsPage() {
  const { data: timesheets, isLoading } = useTimesheets();
  const generateTimesheet = useGenerateTimesheet();
  const decideTimesheet = useDecideTimesheet();

  const { data: leaveRequests } = useLeaveRequests();
  const createLeave = useCreateLeaveRequest();
  const decideLeave = useDecideLeaveRequest();

  const [tsForm, setTsForm] = useState({ employee_id: "", period_start: "", period_end: "", hours_or_units: "", rate_applied: "" });
  const [showTsForm, setShowTsForm] = useState(false);

  const [leaveForm, setLeaveForm] = useState({ employee_id: "", leave_type: "annual", start_date: "", end_date: "" });
  const [showLeaveForm, setShowLeaveForm] = useState(false);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    await generateTimesheet.mutateAsync(tsForm);
    setTsForm({ employee_id: "", period_start: "", period_end: "", hours_or_units: "", rate_applied: "" });
    setShowTsForm(false);
  }

  async function handleLeave(e: React.FormEvent) {
    e.preventDefault();
    await createLeave.mutateAsync(leaveForm);
    setLeaveForm({ employee_id: "", leave_type: "annual", start_date: "", end_date: "" });
    setShowLeaveForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Workforce Management"
        title="Timesheets & Leave"
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" onClick={() => setShowLeaveForm((v) => !v)}>
              {showLeaveForm ? "Cancel" : "New leave request"}
            </Button>
            <Button onClick={() => setShowTsForm((v) => !v)}>{showTsForm ? "Cancel" : "Generate timesheet"}</Button>
          </div>
        }
      />

      {showTsForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleGenerate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr 1fr auto", gap: 8 }}>
            <Input required placeholder="Employee ID" value={tsForm.employee_id} onChange={(e) => setTsForm({ ...tsForm, employee_id: e.target.value })} />
            <Input required type="date" value={tsForm.period_start} onChange={(e) => setTsForm({ ...tsForm, period_start: e.target.value })} />
            <Input required type="date" value={tsForm.period_end} onChange={(e) => setTsForm({ ...tsForm, period_end: e.target.value })} />
            <Input required placeholder="Hours/units" value={tsForm.hours_or_units} onChange={(e) => setTsForm({ ...tsForm, hours_or_units: e.target.value })} />
            <Input required placeholder="Rate" value={tsForm.rate_applied} onChange={(e) => setTsForm({ ...tsForm, rate_applied: e.target.value })} />
            <Button type="submit" disabled={generateTimesheet.isPending}>Generate</Button>
          </form>
        </Card>
      )}

      {showLeaveForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleLeave} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr auto", gap: 8 }}>
            <Input required placeholder="Employee ID" value={leaveForm.employee_id} onChange={(e) => setLeaveForm({ ...leaveForm, employee_id: e.target.value })} />
            <select
              value={leaveForm.leave_type}
              onChange={(e) => setLeaveForm({ ...leaveForm, leave_type: e.target.value })}
              style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
            >
              <option value="annual">Annual</option>
              <option value="sick">Sick</option>
              <option value="unpaid">Unpaid</option>
            </select>
            <Input required type="date" value={leaveForm.start_date} onChange={(e) => setLeaveForm({ ...leaveForm, start_date: e.target.value })} />
            <Input required type="date" value={leaveForm.end_date} onChange={(e) => setLeaveForm({ ...leaveForm, end_date: e.target.value })} />
            <Button type="submit" disabled={createLeave.isPending}>Submit</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !timesheets?.length ? (
        <EmptyState title="No timesheets yet" hint="Generate one from attendance or manual hours/units." />
      ) : (
        <Card style={{ padding: 0, marginBottom: 20 }}>
          <Table>
            <thead><tr><Th>Period</Th><Th>Gross amount</Th><Th>Status</Th><Th></Th></tr></thead>
            <tbody>
              {timesheets.map((t: any) => (
                <tr key={t.id}>
                  <Td mono>{t.period_start} → {t.period_end}</Td>
                  <Td mono>{t.gross_amount}</Td>
                  <Td><Badge tone={STATUS_TONE[t.status] ?? "neutral"}>{t.status}</Badge></Td>
                  <Td>
                    {t.status === "pending_approval" && (
                      <div style={{ display: "flex", gap: 10 }}>
                        <button onClick={() => decideTimesheet.mutate({ timesheetId: t.id, decision: "approve" })} style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Approve</button>
                        <button onClick={() => decideTimesheet.mutate({ timesheetId: t.id, decision: "reject" })} style={{ background: "none", border: "none", color: "var(--sf-brick)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Reject</button>
                      </div>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {leaveRequests?.length ? (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead><tr><Th>Type</Th><Th>Dates</Th><Th>Status</Th><Th></Th></tr></thead>
            <tbody>
              {leaveRequests.map((l: any) => (
                <tr key={l.id}>
                  <Td>{l.leave_type}</Td>
                  <Td mono>{l.start_date} → {l.end_date}</Td>
                  <Td><Badge tone={STATUS_TONE[l.status] ?? "neutral"}>{l.status}</Badge></Td>
                  <Td>
                    {l.status === "pending" && (
                      <div style={{ display: "flex", gap: 10 }}>
                        <button onClick={() => decideLeave.mutate({ leaveId: l.id, decision: "approved" })} style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Approve</button>
                        <button onClick={() => decideLeave.mutate({ leaveId: l.id, decision: "rejected" })} style={{ background: "none", border: "none", color: "var(--sf-brick)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Reject</button>
                      </div>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      ) : null}
    </div>
  );
}
