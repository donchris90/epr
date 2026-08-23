import { Link } from "react-router-dom";
import { PageHeader, Card, Table, Th, Td, Badge } from "../../components/ui";
import { useAgreements } from "../hooks";

function statusTone(status: string): "green" | "amber" | "neutral" | "brick" {
  if (status === "active") return "green";
  if (status === "completed") return "neutral";
  if (status === "terminated") return "brick";
  return "neutral";
}

export default function AgreementsPage() {
  const { agreements, error, loading } = useAgreements();

  return (
    <div>
      <PageHeader eyebrow="Subcontractor Portal" title="Agreements" />

      {error && <div style={{ color: "var(--sf-brick)", fontSize: 13, marginBottom: 16 }}>{error}</div>}

      <Card style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : !agreements || agreements.length === 0 ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>No agreements assigned yet.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Agreement number</Th>
                <Th>Value</Th>
                <Th>Retention</Th>
                <Th>Status</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {agreements.map((a) => (
                <tr key={a.id}>
                  <Td>{a.agreement_number}</Td>
                  <Td mono>{a.currency} {Number(a.value).toLocaleString()}</Td>
                  <Td mono>{a.retention_percentage}%</Td>
                  <Td>
                    <Badge tone={statusTone(a.status)}>{a.status}</Badge>
                  </Td>
                  <Td style={{ textAlign: "right" }}>
                    <Link to={`/subcontractor/agreements/${a.id}`}>View</Link>
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
