import { Link } from "react-router-dom";
import { PageHeader, Card, Badge } from "../../components/ui";
import { useSubcontractorProfile, useAgreements } from "../hooks";
import type { SubcontractAgreement } from "../types";

function statusTone(status: string): "green" | "amber" | "neutral" | "brick" {
  if (status === "active") return "green";
  if (status === "completed") return "neutral";
  if (status === "terminated") return "brick";
  return "neutral";
}

function AgreementCard({ agreement }: { agreement: SubcontractAgreement }) {
  return (
    <Link to={`/subcontractor/agreements/${agreement.id}`} style={{ textDecoration: "none", color: "inherit" }}>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--sf-navy-900)" }}>{agreement.agreement_number}</div>
          <Badge tone={statusTone(agreement.status)}>{agreement.status}</Badge>
        </div>
        <div style={{ fontSize: 13, color: "var(--sf-navy-600)" }}>
          Value: <span className="sf-mono">{agreement.currency} {Number(agreement.value).toLocaleString()}</span>
        </div>
        <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 4 }}>
          Retention: {agreement.retention_percentage}%
        </div>
      </Card>
    </Link>
  );
}

/** Real dashboard, backed by GET /v1/scp/portal-users/<id>/agreements
 * (built alongside this frontend -- a real, previously missing gap,
 * see docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md). No cross-agreement
 * "outstanding submissions" or "notifications" summary here --
 * neither has any real backend aggregation to show honestly (no
 * notification triggers exist for this flow at all, confirmed
 * directly against app/modules/scp/services.py). Each agreement's own
 * detail page has the real, per-agreement progress/claims/certificate
 * data instead. */
export default function DashboardPage() {
  const { profile } = useSubcontractorProfile();
  const { agreements, error, loading } = useAgreements();

  return (
    <div>
      <PageHeader eyebrow="Welcome" title={profile?.email ?? "Your Dashboard"} />

      {loading ? (
        <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
      ) : error ? (
        <div style={{ color: "var(--sf-brick)", fontSize: 13 }}>{error}</div>
      ) : !agreements || agreements.length === 0 ? (
        <Card>
          <p style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>
            No agreements assigned yet. Your contact at the contractor will assign one, and it will appear here.
          </p>
        </Card>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
          {agreements.map((a) => (
            <AgreementCard key={a.id} agreement={a} />
          ))}
        </div>
      )}
    </div>
  );
}
