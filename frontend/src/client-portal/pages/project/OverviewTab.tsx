import { useParams } from "react-router-dom";
import { Card } from "../../../components/ui";
import { useClientProgress, useClientCertificates, useClientVariationOrders, useClientRequests } from "../../hooks";

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: "var(--sf-navy-900)" }}>{value}</div>
    </div>
  );
}

/** Overview (item 3): a real, computed snapshot -- not a placeholder
 * grid. Every number here is derived from data the other tabs show in
 * full; this just rolls it up to one screen. */
export default function OverviewTab() {
  const { projectId } = useParams<{ projectId: string }>();
  const progress = useClientProgress(projectId);
  const certificates = useClientCertificates(projectId);
  const variations = useClientVariationOrders(projectId);
  const requests = useClientRequests(projectId);

  const pendingCertificates = (certificates.data ?? []).filter((c: any) => c.status === "submitted").length;
  const pendingVariations = (variations.data ?? []).filter((v: any) => v.status === "pending").length;
  const openRequests = (requests.data ?? []).filter((r: any) => r.status !== "resolved").length;

  return (
    <div className="row g-3">
      <div className="col-6 col-lg-3">
        <Card>
          <Stat label="Overall progress" value={progress.data?.overall_percent_complete != null ? `${progress.data.overall_percent_complete}%` : "—"} />
        </Card>
      </div>
      <div className="col-6 col-lg-3">
        <Card>
          <Stat label="Certificates awaiting your decision" value={pendingCertificates} />
        </Card>
      </div>
      <div className="col-6 col-lg-3">
        <Card>
          <Stat label="Variations awaiting your decision" value={pendingVariations} />
        </Card>
      </div>
      <div className="col-6 col-lg-3">
        <Card>
          <Stat label="Open issues & requests" value={openRequests} />
        </Card>
      </div>
    </div>
  );
}
