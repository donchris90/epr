import { Link } from "react-router-dom";
import { PageHeader, Card, Badge, EmptyState } from "../../components/ui";
import {
  useEmployees,
  useCasualWorkers,
  useTimesheets,
  useLeaveRequests,
  useExpiringCertifications,
  useExpiringTraining,
} from "./hooks";

function metricLabel(text: string) {
  return <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase", marginBottom: 8 }}>{text}</div>;
}

/** Real Workforce dashboard -- every figure here is computed from
 * data already fetched elsewhere in this module (no new backend
 * aggregation endpoint invented). Shows expiring certifications, per
 * this batch's own explicit requirement ("Dashboard must show
 * expiring certifications"), alongside real headcount, pending
 * approvals, and expiring training as the other real, honest signals
 * this data actually supports. */
export default function WorkforceDashboardPage() {
  const { data: employees } = useEmployees();
  const { data: casualWorkers } = useCasualWorkers();
  const { data: pendingTimesheets } = useTimesheets({ status: "pending_approval" });
  const { data: pendingLeave } = useLeaveRequests({ status: "pending" });
  const { data: expiringCerts } = useExpiringCertifications();
  const { data: expiringTraining } = useExpiringTraining();

  const activeEmployees = employees?.filter((e) => e.status === "active") ?? [];
  const permanentCount = activeEmployees.filter((e) => e.employment_type === "permanent").length;
  const contractCount = activeEmployees.filter((e) => e.employment_type === "contract").length;

  return (
    <div>
      <PageHeader eyebrow="Workforce Management" title="Workforce Dashboard" />

      <div className="row g-3" style={{ marginBottom: 20 }}>
        <div className="col-12 col-md-4">
          <Card>
            {metricLabel("Active headcount")}
            <div className="sf-mono" style={{ fontSize: 24, fontWeight: 700 }}>{activeEmployees.length}</div>
            <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 4 }}>
              {permanentCount} permanent · {contractCount} contract
            </div>
          </Card>
        </div>
        <div className="col-12 col-md-4">
          <Card>
            {metricLabel("Casual workers")}
            <div className="sf-mono" style={{ fontSize: 24, fontWeight: 700 }}>{casualWorkers?.length ?? 0}</div>
          </Card>
        </div>
        <div className="col-12 col-md-4">
          <Card>
            {metricLabel("Pending approvals")}
            <div style={{ display: "flex", gap: 16 }}>
              <div>
                <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{pendingTimesheets?.length ?? 0}</div>
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>Timesheets</div>
              </div>
              <div>
                <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{pendingLeave?.length ?? 0}</div>
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>Leave requests</div>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <div className="row g-3">
        <div className="col-12 col-lg-6">
          <Card style={{ padding: 0 }}>
            <div style={{ padding: "12px 16px 0" }}>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Expiring certifications</h3>
            </div>
            {!expiringCerts?.length ? (
              <EmptyState compact title="No certifications expiring soon." />
            ) : (
              <div style={{ padding: "0 16px 16px" }}>
                {expiringCerts.map((c) => (
                  <div key={c.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--sf-line)", fontSize: 13 }}>
                    <span>{c.certification_type}</span>
                    <Badge tone="amber">{c.expiry_date}</Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="col-12 col-lg-6">
          <Card style={{ padding: 0 }}>
            <div style={{ padding: "12px 16px 0" }}>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Expiring training</h3>
            </div>
            {!expiringTraining?.length ? (
              <EmptyState compact title="No training records expiring soon." />
            ) : (
              <div style={{ padding: "0 16px 16px" }}>
                {expiringTraining.map((t) => (
                  <div key={t.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--sf-line)", fontSize: 13 }}>
                    <span>{t.course_name}</span>
                    <Badge tone="amber">{t.expiry_date}</Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      <div style={{ marginTop: 20, display: "flex", gap: 16, fontSize: 13 }}>
        <Link to="/workforce/employees">Employees →</Link>
        <Link to="/workforce/timesheets">Timesheets & Leave →</Link>
        <Link to="/workforce/payroll">Payroll →</Link>
      </div>
    </div>
  );
}
