import { useParams } from "react-router-dom";
import { PageHeader, Card, Badge, formatMoney } from "../../components/ui";
import { useContract } from "./hooks";

export default function ContractDetailPage() {
  const { contractId } = useParams();
  const { data: contract } = useContract(contractId);

  if (!contract) return <p>Loading…</p>;

  return (
    <div>
      <PageHeader
        eyebrow="Tender-to-Contract"
        title={contract.contract_number}
        action={<Badge tone={contract.status === "active" ? "steel" : "green"}>{contract.status}</Badge>}
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
        <Card>
          <div className="sf-mono" style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 4 }}>
            CONTRACT VALUE
          </div>
          <div style={{ fontSize: 20, fontWeight: 700 }} className="sf-mono">
            {formatMoney(contract.contract_value, contract.currency)}
          </div>
        </Card>
        <Card>
          <div className="sf-mono" style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 4 }}>
            COMPLETION DATE
          </div>
          <div style={{ fontSize: 20, fontWeight: 700 }} className="sf-mono">
            {contract.completion_date ? new Date(contract.completion_date).toLocaleDateString() : "—"}
          </div>
        </Card>
        <Card>
          <div className="sf-mono" style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 4 }}>
            CERTIFICATION CYCLE
          </div>
          <div style={{ fontSize: 20, fontWeight: 700 }} className="sf-mono">
            {contract.certification_frequency || "—"}
          </div>
        </Card>
      </div>

      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 20 }}>
        Retention, bonds, guarantees, and amendment history are available via the API
        (<code className="sf-mono">/v1/ctm/contracts/{contractId}/…</code>) — dedicated panels for these are next
        on the frontend roadmap.
      </p>
    </div>
  );
}
