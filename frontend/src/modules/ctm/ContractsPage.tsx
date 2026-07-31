import { Link } from "react-router-dom";
import { PageHeader, Card, Table, Th, Td, Badge, EmptyState, formatMoney } from "../../components/ui";
import { useContracts, useExpiringInstruments } from "./hooks";

export default function ContractsPage() {
  const { data: contracts, isLoading } = useContracts();
  const { data: expiring } = useExpiringInstruments(30);

  const expiringCount =
    (expiring?.performance_bonds?.length || 0) + (expiring?.insurances?.length || 0) + (expiring?.guarantees?.length || 0);

  return (
    <div>
      <PageHeader eyebrow="Tender-to-Contract" title="Contracts" />

      {expiringCount > 0 && (
        <Card style={{ marginBottom: 20, borderColor: "var(--sf-amber)", background: "var(--sf-amber-dim)" }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>
            {expiringCount} instrument{expiringCount > 1 ? "s" : ""} expiring within 30 days
          </div>
          <div style={{ fontSize: 12, color: "var(--sf-navy-600)" }}>
            Performance bonds, insurance policies, and guarantees nearing expiry need renewal or release action.
          </div>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !contracts?.length ? (
        <EmptyState title="No contracts yet" hint="Contracts are created when a tender is awarded — see the tender's detail page." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Contract no.</Th>
                <Th>Value</Th>
                <Th>Status</Th>
                <Th>Completion date</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((c: any) => (
                <tr key={c.id}>
                  <Td mono>{c.contract_number}</Td>
                  <Td mono>{formatMoney(c.contract_value, c.currency)}</Td>
                  <Td>
                    <Badge tone={c.status === "active" ? "steel" : c.status === "completed" ? "green" : "brick"}>
                      {c.status}
                    </Badge>
                  </Td>
                  <Td mono>{c.completion_date ? new Date(c.completion_date).toLocaleDateString() : "—"}</Td>
                  <Td>
                    <Link to={`/contracts/${c.id}`} style={{ fontSize: 12, fontWeight: 600 }}>
                      Open →
                    </Link>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
