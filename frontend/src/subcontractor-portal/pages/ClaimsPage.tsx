import { Link } from "react-router-dom";
import { PageHeader, Card, Table, Th, Td, Badge, formatMoney } from "../../components/ui";
import { useAgreements, useClaims } from "../hooks";
import type { SubcontractAgreement } from "../types";

function statusTone(status: string): "green" | "amber" | "neutral" | "brick" {
  if (status === "approved" || status === "paid") return "green";
  if (status === "rejected") return "brick";
  return "amber";
}

function AgreementClaims({ agreement }: { agreement: SubcontractAgreement }) {
  const { claims } = useClaims(agreement.id);
  if (!claims || claims.length === 0) return null;

  return (
    <Card style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
        <Link to={`/subcontractor/agreements/${agreement.id}`}>{agreement.agreement_number}</Link>
      </div>
      <Table>
        <thead>
          <tr>
            <Th>Type</Th>
            <Th>Description</Th>
            <Th>Amount</Th>
            <Th>Status</Th>
            <Th>Submitted</Th>
          </tr>
        </thead>
        <tbody>
          {claims.map((c) => (
            <tr key={c.id}>
              <Td>{c.claim_type.replace(/_/g, " ")}</Td>
              <Td>{c.description}</Td>
              <Td mono>{c.claimed_amount ? formatMoney(c.claimed_amount) : "—"}</Td>
              <Td>
                <Badge tone={statusTone(c.status)}>{c.status}</Badge>
              </Td>
              <Td mono>{new Date(c.submitted_at).toLocaleDateString()}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

/** Real, top-level claims view -- there's no single "all my claims"
 * endpoint (confirmed directly against
 * backend/app/modules/scp/routes.py: GET .../claims requires a real
 * agreement_id query param), so this genuinely fetches claims
 * per-agreement and groups them, rather than pretending a
 * cross-agreement endpoint exists. To submit a new claim, use the
 * relevant agreement's own detail page -- keeps claim creation
 * grounded in the specific agreement it belongs to. */
export default function ClaimsPage() {
  const { agreements, loading } = useAgreements();

  return (
    <div>
      <PageHeader eyebrow="Subcontractor Portal" title="Claims" />
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 16 }}>
        To submit a new claim, open the relevant agreement and use its Claims section.
      </p>

      {loading ? (
        <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
      ) : !agreements || agreements.length === 0 ? (
        <Card>
          <p style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>No agreements assigned yet.</p>
        </Card>
      ) : (
        agreements.map((a) => <AgreementClaims key={a.id} agreement={a} />)
      )}
    </div>
  );
}
