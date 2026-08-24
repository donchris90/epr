import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { useEmployees, useCreateEmployee, useCasualWorkers, useCreateCasualWorker, useExpiringCertifications } from "./hooks";

export default function EmployeesPage() {
  const { data: employees, isLoading } = useEmployees();
  const createEmployee = useCreateEmployee();
  const { data: casualWorkers } = useCasualWorkers();
  const createCasualWorker = useCreateCasualWorker();
  const { data: expiringCerts } = useExpiringCertifications();

  const [showEmpForm, setShowEmpForm] = useState(false);
  const [empForm, setEmpForm] = useState({ name: "", role: "", trade: "", employment_type: "permanent" });

  const [showCasualForm, setShowCasualForm] = useState(false);
  const [casualForm, setCasualForm] = useState({ name: "", phone: "", daily_rate: "" });

  async function handleCreateEmployee(e: React.FormEvent) {
    e.preventDefault();
    await createEmployee.mutateAsync(empForm);
    setEmpForm({ name: "", role: "", trade: "", employment_type: "permanent" });
    setShowEmpForm(false);
  }

  async function handleCreateCasual(e: React.FormEvent) {
    e.preventDefault();
    await createCasualWorker.mutateAsync(casualForm);
    setCasualForm({ name: "", phone: "", daily_rate: "" });
    setShowCasualForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Workforce Management"
        title="Employees & Casual Workers"
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" onClick={() => setShowCasualForm((v) => !v)}>
              {showCasualForm ? "Cancel" : "New casual worker"}
            </Button>
            <Button onClick={() => setShowEmpForm((v) => !v)}>{showEmpForm ? "Cancel" : "New employee"}</Button>
          </div>
        }
      />

      {expiringCerts?.length ? (
        <Card style={{ marginBottom: 20, borderColor: "var(--sf-amber)" }}>
          <div style={{ fontSize: 13, color: "#8a5f14", fontWeight: 600 }}>
            {expiringCerts.length} certification(s) expiring soon
          </div>
        </Card>
      ) : null}

      {showEmpForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreateEmployee} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr auto", gap: 12 }}>
            <Field label="Name">
              <Input required value={empForm.name} onChange={(e) => setEmpForm({ ...empForm, name: e.target.value })} />
            </Field>
            <Field label="Role">
              <Input value={empForm.role} onChange={(e) => setEmpForm({ ...empForm, role: e.target.value })} />
            </Field>
            <Field label="Trade">
              <Input value={empForm.trade} onChange={(e) => setEmpForm({ ...empForm, trade: e.target.value })} />
            </Field>
            <Field label="Employment type">
              <select
                value={empForm.employment_type}
                onChange={(e) => setEmpForm({ ...empForm, employment_type: e.target.value })}
                style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
              >
                <option value="permanent">Permanent</option>
                <option value="contract">Contract</option>
              </select>
            </Field>
            <Button type="submit" disabled={createEmployee.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {showCasualForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreateCasual} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 12 }}>
            <Field label="Name">
              <Input required value={casualForm.name} onChange={(e) => setCasualForm({ ...casualForm, name: e.target.value })} />
            </Field>
            <Field label="Phone">
              <Input value={casualForm.phone} onChange={(e) => setCasualForm({ ...casualForm, phone: e.target.value })} />
            </Field>
            <Field label="Daily rate">
              <Input value={casualForm.daily_rate} onChange={(e) => setCasualForm({ ...casualForm, daily_rate: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createCasualWorker.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !employees?.length ? (
        <EmptyState title="No employees yet" hint="Register employees to start tracking attendance and timesheets." />
      ) : (
        <Card style={{ padding: 0, marginBottom: 20 }}>
          <Table>
            <thead><tr><Th>Name</Th><Th>Role</Th><Th>Trade</Th><Th>Type</Th><Th>Status</Th></tr></thead>
            <tbody>
              {employees.map((e) => (
                <tr key={e.id}>
                  <Td><Link to={`/workforce/employees/${e.id}`}>{e.name}</Link></Td>
                  <Td>{e.role || "—"}</Td>
                  <Td>{e.trade || "—"}</Td>
                  <Td><Badge tone="neutral">{e.employment_type}</Badge></Td>
                  <Td><Badge tone={e.status === "active" ? "green" : "neutral"}>{e.status}</Badge></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {casualWorkers?.length ? (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead><tr><Th>Name</Th><Th>Phone</Th><Th>Daily rate</Th></tr></thead>
            <tbody>
              {casualWorkers.map((w) => (
                <tr key={w.id}>
                  <Td>{w.name}</Td>
                  <Td mono>{w.phone || "—"}</Td>
                  <Td mono>{w.daily_rate || "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      ) : null}
    </div>
  );
}
