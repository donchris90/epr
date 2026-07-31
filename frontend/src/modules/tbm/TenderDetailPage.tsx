import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input } from "../../components/ui";
import {
  useTender,
  useBOQItems,
  useAddBOQItem,
  useAddChecklistItem,
  useSubmissionReadiness,
  useSubmitTender,
} from "./hooks";

export default function TenderDetailPage() {
  const { tenderId } = useParams();
  const { data: tender } = useTender(tenderId);
  const { data: boqItems } = useBOQItems(tenderId);
  const addBOQItem = useAddBOQItem(tenderId);
  const addChecklistItem = useAddChecklistItem(tenderId);
  const { data: readiness, refetch: refetchReadiness } = useSubmissionReadiness(tenderId);
  const submitTender = useSubmitTender(tenderId);

  const [itemDescription, setItemDescription] = useState("");
  const [itemUnit, setItemUnit] = useState("");
  const [itemQty, setItemQty] = useState("");
  const [checklistLabel, setChecklistLabel] = useState("");

  async function handleAddBOQItem(e: React.FormEvent) {
    e.preventDefault();
    await addBOQItem.mutateAsync({ description: itemDescription, unit: itemUnit || undefined, quantity: itemQty || undefined });
    setItemDescription("");
    setItemUnit("");
    setItemQty("");
  }

  async function handleAddChecklistItem(e: React.FormEvent) {
    e.preventDefault();
    await addChecklistItem.mutateAsync({ label: checklistLabel });
    setChecklistLabel("");
    refetchReadiness();
  }

  async function handleSubmit() {
    await submitTender.mutateAsync({ method: "portal", submitted_at: new Date().toISOString() });
  }

  if (!tender) return <p>Loading…</p>;

  return (
    <div>
      <PageHeader
        eyebrow="Tender-to-Contract"
        title={tender.reference_number}
        action={
          <Badge tone={tender.status === "submitted" ? "steel" : tender.status === "awarded" ? "green" : "neutral"}>
            {tender.status.replace(/_/g, " ")}
          </Badge>
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>BOQ items</h3>
            <form onSubmit={handleAddBOQItem} style={{ display: "grid", gridTemplateColumns: "3fr 1fr 1fr auto", gap: 8, marginBottom: 16 }}>
              <Input required placeholder="Description" value={itemDescription} onChange={(e) => setItemDescription(e.target.value)} />
              <Input placeholder="Unit" value={itemUnit} onChange={(e) => setItemUnit(e.target.value)} />
              <Input placeholder="Qty" value={itemQty} onChange={(e) => setItemQty(e.target.value)} />
              <Button type="submit" variant="secondary" disabled={addBOQItem.isPending}>
                Add
              </Button>
            </form>

            {boqItems?.length ? (
              <Table>
                <thead>
                  <tr>
                    <Th>Description</Th>
                    <Th>Unit</Th>
                    <Th>Qty</Th>
                  </tr>
                </thead>
                <tbody>
                  {boqItems.map((item: any) => (
                    <tr key={item.id}>
                      <Td>{item.description}</Td>
                      <Td mono>{item.unit || "—"}</Td>
                      <Td mono>{item.quantity || "—"}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No BOQ items imported yet.</p>
            )}
          </Card>

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Checklist</h3>
            <form onSubmit={handleAddChecklistItem} style={{ display: "flex", gap: 8 }}>
              <Input required placeholder="e.g. Bid bond obtained" value={checklistLabel} onChange={(e) => setChecklistLabel(e.target.value)} />
              <Button type="submit" variant="secondary" disabled={addChecklistItem.isPending}>
                Add
              </Button>
            </form>
          </Card>
        </div>

        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Submission readiness</h3>
            {readiness?.can_submit ? (
              <Badge tone="green">Ready to submit</Badge>
            ) : (
              <div>
                <Badge tone="amber">Blocked</Badge>
                <ul style={{ fontSize: 12, marginTop: 10, paddingLeft: 16, color: "var(--sf-navy-600)" }}>
                  {readiness?.blockers?.map((b: string, i: number) => (
                    <li key={i} style={{ marginBottom: 4 }}>
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <Button
              style={{ marginTop: 14, width: "100%" }}
              disabled={!readiness?.can_submit || tender.status === "submitted" || submitTender.isPending}
              onClick={handleSubmit}
            >
              {tender.status === "submitted" ? "Submitted" : "Submit tender"}
            </Button>
          </Card>

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 8 }}>Estimating</h3>
            <p style={{ fontSize: 12, color: "var(--sf-navy-600)", marginBottom: 12 }}>
              Price this tender's BOQ and build the tender price document.
            </p>
            <Link to={`/tenders/${tenderId}/estimate`} style={{ fontSize: 13, fontWeight: 600 }}>
              Open estimate →
            </Link>
          </Card>
        </div>
      </div>
    </div>
  );
}
