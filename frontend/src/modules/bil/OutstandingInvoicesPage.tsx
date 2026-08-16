import { PageHeader, Card, Table, Th, Td, Badge, EmptyState } from "../../components/ui";
import { useOutstandingInvoices } from "./hooks";

const BAND_LABELS: Record<string, string> = {
  current: "Current",
  "1_30_days": "1–30 days overdue",
  "31_60_days": "31–60 days overdue",
  "61_90_days": "61–90 days overdue",
  over_90_days: "Over 90 days overdue",
};

const BAND_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  current: "green",
  "1_30_days": "steel",
  "31_60_days": "amber",
  "61_90_days": "amber",
  over_90_days: "brick",
};

export default function OutstandingInvoicesPage() {
  const { data, isLoading } = useOutstandingInvoices();

  if (isLoading) return <p>Loading…</p>;

  const bands = data ?? {};
  const hasAny = Object.values(bands).some((items: any) => items?.length > 0);

  return (
    <div>
      <PageHeader eyebrow="Client Billing" title="Outstanding Invoices" />

      {!hasAny ? (
        <EmptyState title="Nothing outstanding" hint="Every submitted certificate has either been paid or hasn't reached its due date." />
      ) : (
        Object.entries(BAND_LABELS).map(([band, label]) => {
          const items = bands[band] ?? [];
          if (!items.length) return null;
          return (
            <Card key={band} style={{ marginBottom: 16, padding: 0 }}>
              <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--sf-line)" }}>
                <Badge tone={BAND_TONE[band]}>{label}</Badge>
              </div>
              <Table>
                <thead>
                  <tr>
                    <Th>Certificate</Th>
                    <Th>Amount</Th>
                    <Th>Due date</Th>
                    <Th>Status</Th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item: any) => (
                    <tr key={item.certificate_id}>
                      <Td mono>{item.certificate_number}</Td>
                      <Td mono>{item.amount}</Td>
                      <Td mono>{item.due_date ?? "—"}</Td>
                      <Td>{item.status}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          );
        })
      )}
    </div>
  );
}
