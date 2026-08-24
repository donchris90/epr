import { Link } from "react-router-dom";
import { PageHeader, Card, formatMoney } from "../../components/ui";
import { useSubcontractors, useAgreements } from "./hooks";

function metricLabel(text: string) {
  return <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase", marginBottom: 8 }}>{text}</div>;
}

/** Real Subcontractor dashboard -- computed entirely from the two
 * tenant-wide lists this module already exposes cheaply
 * (GET /sub/subcontractors, GET /sub/agreements), matching this
 * batch's own established "don't fetch thousands of records
 * unnecessarily" discipline. Deliberately does NOT show aggregate
 * claims/certificates/compliance/performance counts: those are only
 * ever available per-agreement or per-subcontractor (no tenant-wide
 * list endpoint exists for any of them), and fetching every
 * agreement's own claims/certificates just to sum a dashboard number
 * would be a real N+1 query pattern -- see
 * docs/WFM_SUB_GAPS.md. */
export default function SubcontractorDashboardPage() {
  const { data: subcontractors } = useSubcontractors();
  const { data: agreements } = useAgreements();

  const activeSubcontractors = subcontractors?.filter((s) => s.status === "active") ?? [];
  const activeAgreements = agreements?.filter((a) => a.status === "active") ?? [];
  const totalValue = activeAgreements.reduce((sum, a) => sum + Number(a.value), 0);

  const agreementsByStatus = (agreements ?? []).reduce<Record<string, number>>((acc, a) => {
    acc[a.status] = (acc[a.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      <PageHeader eyebrow="Subcontractor Management" title="Subcontractor Dashboard" />

      <div className="row g-3" style={{ marginBottom: 20 }}>
        <div className="col-12 col-md-4">
          <Card>
            {metricLabel("Active subcontractors")}
            <div className="sf-mono" style={{ fontSize: 24, fontWeight: 700 }}>{activeSubcontractors.length}</div>
            <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 4 }}>
              {subcontractors?.length ?? 0} total on file
            </div>
          </Card>
        </div>
        <div className="col-12 col-md-4">
          <Card>
            {metricLabel("Active agreements")}
            <div className="sf-mono" style={{ fontSize: 24, fontWeight: 700 }}>{activeAgreements.length}</div>
            <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 4 }}>
              {agreements?.length ?? 0} total on file
            </div>
          </Card>
        </div>
        <div className="col-12 col-md-4">
          <Card>
            {metricLabel("Total active agreement value")}
            <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{formatMoney(totalValue)}</div>
          </Card>
        </div>
      </div>

      <Card>
        {metricLabel("Agreements by status")}
        {Object.keys(agreementsByStatus).length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>No agreements yet.</p>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
            {Object.entries(agreementsByStatus).map(([status, count]) => (
              <div key={status}>
                <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{count}</div>
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>{status}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div style={{ marginTop: 20, display: "flex", gap: 16, fontSize: 13 }}>
        <Link to="/subcontractors/list">Subcontractors & Agreements →</Link>
      </div>
    </div>
  );
}
