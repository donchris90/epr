import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, Field, formatMoney } from "../../components/ui";
import {
  useEstimateVersions,
  useCreateEstimateVersion,
  useSubmitEstimateVersion,
  useBOQItems,
  useAddBOQItem,
  useSaveRateAnalysis,
  useTenderPrice,
  useGenerateCBS,
} from "./hooks";

function RateAnalysisForm({ boqItemId, versionId, onDone }: { boqItemId: string; versionId: string; onDone: () => void }) {
  const saveRateAnalysis = useSaveRateAnalysis(versionId);
  const [material, setMaterial] = useState("0");
  const [labor, setLabor] = useState("0");
  const [equipment, setEquipment] = useState("0");
  const [markup, setMarkup] = useState("10");

  async function handleSave() {
    await saveRateAnalysis.mutateAsync({
      boqItemId,
      lines: [
        { component_type: "material", description: "Material", quantity_per_unit: "1", unit_cost: material },
        { component_type: "labor", description: "Labor", quantity_per_unit: "1", unit_cost: labor },
        { component_type: "equipment", description: "Equipment", quantity_per_unit: "1", unit_cost: equipment },
      ],
      markupPct: markup,
    });
    onDone();
  }

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-end", padding: "10px 0" }}>
      <Field label="Material/unit">
        <Input value={material} onChange={(e) => setMaterial(e.target.value)} />
      </Field>
      <Field label="Labor/unit">
        <Input value={labor} onChange={(e) => setLabor(e.target.value)} />
      </Field>
      <Field label="Equipment/unit">
        <Input value={equipment} onChange={(e) => setEquipment(e.target.value)} />
      </Field>
      <Field label="Markup %">
        <Input value={markup} onChange={(e) => setMarkup(e.target.value)} />
      </Field>
      <Button variant="secondary" onClick={handleSave} disabled={saveRateAnalysis.isPending}>
        Save rate
      </Button>
    </div>
  );
}

export default function EstimatePage() {
  const { tenderId } = useParams();
  const { data: versions, isLoading: versionsLoading } = useEstimateVersions(tenderId);
  const createVersion = useCreateEstimateVersion(tenderId);

  const currentVersion = versions?.find((v: any) => v.status !== "superseded") || versions?.[0];
  const versionId = currentVersion?.id;

  const submitVersion = useSubmitEstimateVersion(versionId, tenderId);
  const { data: boqItems } = useBOQItems(versionId);
  const addBOQItem = useAddBOQItem(versionId);
  const { data: tenderPrice, refetch: refetchPrice } = useTenderPrice(versionId);
  const generateCBS = useGenerateCBS(versionId);

  const [pricingItemId, setPricingItemId] = useState<string | null>(null);
  const [itemDescription, setItemDescription] = useState("");
  const [itemUnit, setItemUnit] = useState("");
  const [itemQty, setItemQty] = useState("");
  const [cbsResult, setCbsResult] = useState<string | null>(null);

  async function handleCreateVersion() {
    await createVersion.mutateAsync("Base case");
  }

  async function handleAddItem(e: React.FormEvent) {
    e.preventDefault();
    await addBOQItem.mutateAsync({ description: itemDescription, unit: itemUnit || undefined, quantity: itemQty || undefined });
    setItemDescription("");
    setItemUnit("");
    setItemQty("");
  }

  async function handleGenerateCBS() {
    try {
      await generateCBS.mutateAsync();
      setCbsResult("Cost Breakdown Structure generated.");
    } catch (err: any) {
      setCbsResult(err?.response?.data?.detail || "Could not generate CBS.");
    }
  }

  if (versionsLoading) return <p>Loading…</p>;

  if (!versions?.length) {
    return (
      <div>
        <PageHeader eyebrow="Estimating" title="Estimate" />
        <Card style={{ textAlign: "center", padding: 40 }}>
          <p style={{ marginBottom: 16 }}>No estimate has been started for this tender yet.</p>
          <Button onClick={handleCreateVersion} disabled={createVersion.isPending}>
            Start estimate
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Estimating"
        title={`Estimate — ${currentVersion.label || `v${currentVersion.version_number}`}`}
        action={<Badge tone={currentVersion.status === "submitted" ? "green" : "neutral"}>{currentVersion.status}</Badge>}
      />

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Priced BOQ</h3>
            <form onSubmit={handleAddItem} style={{ display: "grid", gridTemplateColumns: "3fr 1fr 1fr auto", gap: 8, marginBottom: 16 }}>
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
                    <Th>Qty</Th>
                    <Th>Unit rate</Th>
                    <Th></Th>
                  </tr>
                </thead>
                <tbody>
                  {boqItems.map((item: any) => (
                    <>
                      <tr key={item.id}>
                        <Td>{item.description}</Td>
                        <Td mono>
                          {item.quantity || "—"} {item.unit}
                        </Td>
                        <Td mono>{item.unit_rate ? formatMoney(item.unit_rate) : "Not priced"}</Td>
                        <Td>
                          <Button
                            variant="ghost"
                            onClick={() => setPricingItemId(pricingItemId === item.id ? null : item.id)}
                          >
                            {pricingItemId === item.id ? "Close" : "Price →"}
                          </Button>
                        </Td>
                      </tr>
                      {pricingItemId === item.id && (
                        <tr>
                          <td colSpan={4} style={{ borderBottom: "1px solid var(--sf-line)", background: "var(--sf-paper-dim)" }}>
                            <RateAnalysisForm
                              boqItemId={item.id}
                              versionId={versionId}
                              onDone={() => {
                                setPricingItemId(null);
                                refetchPrice();
                              }}
                            />
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No BOQ items yet.</p>
            )}
          </Card>
        </div>

        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Tender price</h3>
            {tenderPrice ? (
              <div style={{ fontSize: 13 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span>Items total</span>
                  <span className="sf-mono">{formatMoney(tenderPrice.items_total)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span>Contingency</span>
                  <span className="sf-mono">{formatMoney(tenderPrice.contingency_total)}</span>
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontWeight: 700,
                    borderTop: "1px solid var(--sf-line)",
                    paddingTop: 8,
                    marginTop: 8,
                  }}
                >
                  <span>Grand total</span>
                  <span className="sf-mono">{formatMoney(tenderPrice.grand_total)}</span>
                </div>
              </div>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>Price BOQ items to see the tender total.</p>
            )}
          </Card>

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Award</h3>
            {currentVersion.status !== "submitted" ? (
              <Button style={{ width: "100%" }} onClick={() => submitVersion.mutate()} disabled={submitVersion.isPending}>
                Submit estimate
              </Button>
            ) : (
              <>
                <Badge tone="green">Submitted — estimate locked</Badge>
                <Button style={{ width: "100%", marginTop: 12 }} variant="secondary" onClick={handleGenerateCBS} disabled={generateCBS.isPending}>
                  Generate Cost Breakdown Structure
                </Button>
                {cbsResult && <p style={{ fontSize: 12, marginTop: 8, color: "var(--sf-navy-600)" }}>{cbsResult}</p>}
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
