import { Fragment, useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input, Field, Select, formatMoney, EmptyState } from "../../components/ui";
import { LoadingState } from "../../components/Loading";
import { useToast } from "../../lib/toast";
import { getErrorMessage } from "../../api/client";
import {
  useEstimateVersions,
  useCreateEstimateVersion,
  useSubmitEstimateVersion,
  useBOQItems,
  useAddBOQItem,
  useRateAnalysis,
  useSaveRateAnalysis,
  useEngineersEstimate,
  useTenderPrice,
  useAddMarkup,
  useAddContingencyItem,
  useCostLibraryItems,
  useCreateCostLibraryItem,
  useMaterialPrices,
  useCreateMaterialPrice,
  useEquipmentRates,
  useCreateEquipmentRate,
  useLaborRates,
  useCreateLaborRate,
  useGenerateCBS,
  useCBS,
  useApproveCBS,
  useCreateBudgetRevision,
  useFinalizeBudgetRevision,
} from "./hooks";
import type { BOQItem, Markup, ContingencyItem } from "./types";

type Tab = "boq" | "breakdown" | "resources" | "cbs";

// --- Rate analysis: expandable row under a BOQ item ------------------------

function RateAnalysisRow({ item, versionId, onSaved }: { item: BOQItem; versionId: string; onSaved: () => void }) {
  const { data: existing } = useRateAnalysis(item.id);
  const saveRateAnalysis = useSaveRateAnalysis(versionId);
  const toast = useToast();

  const [material, setMaterial] = useState("0");
  const [labor, setLabor] = useState("0");
  const [equipment, setEquipment] = useState("0");
  const [subcontract, setSubcontract] = useState("0");
  const [markup, setMarkup] = useState("10");

  const componentSubtotal = existing ? existing.lines.reduce((sum, l) => sum + Number(l.line_total), 0) : null;
  const unitRate = item.unit_rate ? Number(item.unit_rate) : null;
  // Simple subtraction of two real backend numbers (component lines'
  // total vs the reconciled unit rate) -- not a re-derivation of the
  // markup rule itself, which the backend alone owns in
  // save_rate_analysis. This just shows how much of the already-saved
  // unit rate is markup vs direct cost.
  const markupPerUnit = componentSubtotal !== null && unitRate !== null ? unitRate - componentSubtotal : null;

  async function handleSave() {
    try {
      await saveRateAnalysis.mutateAsync({
        boqItemId: item.id,
        lines: [
          { component_type: "material", description: "Material", quantity_per_unit: "1", unit_cost: material },
          { component_type: "labor", description: "Labor", quantity_per_unit: "1", unit_cost: labor },
          { component_type: "equipment", description: "Equipment", quantity_per_unit: "1", unit_cost: equipment },
          { component_type: "subcontract", description: "Subcontract", quantity_per_unit: "1", unit_cost: subcontract },
        ].filter((l) => Number(l.unit_cost) > 0),
        markupPct: markup,
      });
      toast.success("Rate analysis saved.");
      onSaved();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div style={{ padding: 14 }}>
      {existing && componentSubtotal !== null && (
        <div style={{ marginBottom: 12, fontSize: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Current rate analysis</div>
          <Table ariaLabel="Rate analysis lines">
            <thead>
              <tr>
                <Th>Component</Th>
                <Th>Description</Th>
                <Th>Qty/unit</Th>
                <Th>Unit cost</Th>
                <Th>Line total</Th>
              </tr>
            </thead>
            <tbody>
              {existing.lines.map((l) => (
                <tr key={l.id}>
                  <Td>{l.component_type}</Td>
                  <Td>{l.description}</Td>
                  <Td mono>{l.quantity_per_unit}</Td>
                  <Td mono>{l.unit_cost}</Td>
                  <Td mono>{l.line_total}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <div style={{ display: "flex", gap: 20, marginTop: 8 }}>
            <div>
              <div style={{ color: "var(--sf-navy-400)" }}>Direct cost / unit</div>
              <div className="sf-mono" style={{ fontWeight: 600 }}>
                {componentSubtotal.toFixed(4)}
              </div>
            </div>
            <div>
              <div style={{ color: "var(--sf-navy-400)" }}>Markup / unit</div>
              <div className="sf-mono" style={{ fontWeight: 600 }}>
                {markupPerUnit?.toFixed(4)}
              </div>
            </div>
            <div>
              <div style={{ color: "var(--sf-navy-400)" }}>Reconciled unit rate</div>
              <div className="sf-mono" style={{ fontWeight: 600 }}>
                {unitRate?.toFixed(4)}
              </div>
            </div>
          </div>
        </div>
      )}

      <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 8 }}>{existing ? "Re-price this item" : "Price this item"}</div>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
        <Field label="Material/unit">
          <Input value={material} onChange={(e) => setMaterial(e.target.value)} />
        </Field>
        <Field label="Labor/unit">
          <Input value={labor} onChange={(e) => setLabor(e.target.value)} />
        </Field>
        <Field label="Equipment/unit">
          <Input value={equipment} onChange={(e) => setEquipment(e.target.value)} />
        </Field>
        <Field label="Subcontract/unit">
          <Input value={subcontract} onChange={(e) => setSubcontract(e.target.value)} />
        </Field>
        <Field label="Markup %" hint="Applied to this item's cost lines only">
          <Input value={markup} onChange={(e) => setMarkup(e.target.value)} />
        </Field>
        <Button variant="secondary" onClick={handleSave} disabled={saveRateAnalysis.isPending}>
          {existing ? "Save re-price" : "Save rate"}
        </Button>
      </div>
    </div>
  );
}

// --- Resource library tabs (EST-03 through EST-07) --------------------------

function CostLibraryTab() {
  const { data: items } = useCostLibraryItems();
  const create = useCreateCostLibraryItem();
  const toast = useToast();
  const [form, setForm] = useState({ code: "", description: "", component_type: "material", unit: "", default_unit_cost: "" });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync(form);
      toast.success(`"${form.code}" added to the cost library.`);
      setForm({ code: "", description: "", component_type: "material", unit: "", default_unit_cost: "" });
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div>
      <form onSubmit={submit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr 1fr 1fr 1fr auto", gap: 8, marginBottom: 16 }}>
        <Input required placeholder="Code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
        <Input required placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <Select value={form.component_type} onChange={(e) => setForm({ ...form, component_type: e.target.value })}>
          <option value="material">Material</option>
          <option value="labor">Labor</option>
          <option value="equipment">Equipment</option>
          <option value="subcontract">Subcontract</option>
        </Select>
        <Input placeholder="Unit" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
        <Input required placeholder="Default unit cost" value={form.default_unit_cost} onChange={(e) => setForm({ ...form, default_unit_cost: e.target.value })} />
        <Button type="submit" variant="secondary" disabled={create.isPending}>
          Add
        </Button>
      </form>
      {items?.length ? (
        <Table ariaLabel="Cost library items">
          <thead>
            <tr>
              <Th>Code</Th>
              <Th>Description</Th>
              <Th>Type</Th>
              <Th>Default cost</Th>
            </tr>
          </thead>
          <tbody>
            {items.map((i) => (
              <tr key={i.id}>
                <Td mono>{i.code}</Td>
                <Td>{i.description}</Td>
                <Td>{i.component_type}</Td>
                <Td mono>{i.default_unit_cost}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <EmptyState title="No cost library items yet" />
      )}
    </div>
  );
}

function MaterialPricesTab() {
  const { data: prices } = useMaterialPrices();
  const create = useCreateMaterialPrice();
  const toast = useToast();
  const [form, setForm] = useState({ material_name: "", price: "", effective_date: new Date().toISOString().slice(0, 10), location: "", unit: "" });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync(form);
      toast.success(`Price for "${form.material_name}" recorded.`);
      setForm({ ...form, material_name: "", price: "" });
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div>
      <form onSubmit={submit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr auto", gap: 8, marginBottom: 16 }}>
        <Input required placeholder="Material name" value={form.material_name} onChange={(e) => setForm({ ...form, material_name: e.target.value })} />
        <Input placeholder="Location" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
        <Input placeholder="Unit" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
        <Input required placeholder="Price" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
        <Input required type="date" value={form.effective_date} onChange={(e) => setForm({ ...form, effective_date: e.target.value })} />
        <Button type="submit" variant="secondary" disabled={create.isPending}>
          Add
        </Button>
      </form>
      {prices?.length ? (
        <Table ariaLabel="Material prices">
          <thead>
            <tr>
              <Th>Material</Th>
              <Th>Location</Th>
              <Th>Price</Th>
              <Th>Effective</Th>
            </tr>
          </thead>
          <tbody>
            {prices.map((p) => (
              <tr key={p.id}>
                <Td>{p.material_name}</Td>
                <Td>{p.location || "—"}</Td>
                <Td mono>{p.price}</Td>
                <Td mono>{p.effective_date}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <EmptyState title="No material prices recorded yet" />
      )}
    </div>
  );
}

function EquipmentRatesTab() {
  const { data: rates } = useEquipmentRates();
  const create = useCreateEquipmentRate();
  const toast = useToast();
  const [form, setForm] = useState({ equipment_type: "", cost_per_hour: "", source: "owned" });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync(form);
      toast.success(`"${form.equipment_type}" rate recorded.`);
      setForm({ equipment_type: "", cost_per_hour: "", source: "owned" });
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div>
      <form onSubmit={submit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 8, marginBottom: 16 }}>
        <Input required placeholder="Equipment type" value={form.equipment_type} onChange={(e) => setForm({ ...form, equipment_type: e.target.value })} />
        <Select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}>
          <option value="owned">Owned</option>
          <option value="rental">Rental</option>
        </Select>
        <Input required placeholder="Cost/hour" value={form.cost_per_hour} onChange={(e) => setForm({ ...form, cost_per_hour: e.target.value })} />
        <Button type="submit" variant="secondary" disabled={create.isPending}>
          Add
        </Button>
      </form>
      {rates?.length ? (
        <Table ariaLabel="Equipment rates">
          <thead>
            <tr>
              <Th>Type</Th>
              <Th>Source</Th>
              <Th>Cost/hour</Th>
            </tr>
          </thead>
          <tbody>
            {rates.map((r) => (
              <tr key={r.id}>
                <Td>{r.equipment_type}</Td>
                <Td>{r.source}</Td>
                <Td mono>{r.cost_per_hour}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <EmptyState title="No equipment rates recorded yet" />
      )}
    </div>
  );
}

function LaborRatesTab() {
  const { data: rates } = useLaborRates();
  const create = useCreateLaborRate();
  const toast = useToast();
  const [form, setForm] = useState({ trade: "", grade: "", hourly_rate: "", statutory_oncost_pct: "0" });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync(form);
      toast.success(`"${form.trade}" rate recorded.`);
      setForm({ trade: "", grade: "", hourly_rate: "", statutory_oncost_pct: "0" });
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div>
      <form onSubmit={submit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 8, marginBottom: 16 }}>
        <Input required placeholder="Trade" value={form.trade} onChange={(e) => setForm({ ...form, trade: e.target.value })} />
        <Input placeholder="Grade" value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value })} />
        <Input required placeholder="Hourly rate" value={form.hourly_rate} onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })} />
        <Input placeholder="Statutory on-cost %" value={form.statutory_oncost_pct} onChange={(e) => setForm({ ...form, statutory_oncost_pct: e.target.value })} />
        <Button type="submit" variant="secondary" disabled={create.isPending}>
          Add
        </Button>
      </form>
      {rates?.length ? (
        <Table ariaLabel="Labor rates">
          <thead>
            <tr>
              <Th>Trade</Th>
              <Th>Grade</Th>
              <Th>Hourly rate</Th>
              <Th>Statutory on-cost %</Th>
            </tr>
          </thead>
          <tbody>
            {rates.map((r) => (
              <tr key={r.id}>
                <Td>{r.trade}</Td>
                <Td>{r.grade || "—"}</Td>
                <Td mono>{r.hourly_rate}</Td>
                <Td mono>{r.statutory_oncost_pct}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <EmptyState title="No labor rates recorded yet" />
      )}
    </div>
  );
}

// --- Cost breakdown structure & budget revisions ----------------------------

function CBSPanel({ cbsId }: { cbsId: string }) {
  const cbs = useCBS(cbsId);
  const approve = useApproveCBS(cbsId);
  const createRevision = useCreateBudgetRevision(cbsId);
  const finalizeRevision = useFinalizeBudgetRevision(cbsId);
  const toast = useToast();
  const [revisingLineId, setRevisingLineId] = useState<string | null>(null);
  const [revisionReason, setRevisionReason] = useState("");
  const [revisionAmount, setRevisionAmount] = useState("");
  const [pendingRevision, setPendingRevision] = useState<{ id: string; lineItemId: string } | null>(null);

  async function handleApprove() {
    if (!window.confirm("Approve this CBS baseline? Once approved, line amounts can only change via a formal Budget Revision.")) return;
    try {
      await approve.mutateAsync();
      toast.success("CBS approved — baseline is now locked.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleCreateRevision(lineItemId: string) {
    if (!revisionReason.trim() || !revisionAmount.trim()) return;
    try {
      const res = await createRevision.mutateAsync({ cbs_line_item_id: lineItemId, reason: revisionReason.trim(), revised_amount: revisionAmount });
      if (res.data.status === "pending") {
        setPendingRevision({ id: res.data.id, lineItemId });
        toast.success("Revision created — pending approval via this tenant's configured workflow.");
      } else {
        toast.success("Revision created and applied immediately (no approval workflow configured for budget revisions).");
      }
      setRevisingLineId(null);
      setRevisionReason("");
      setRevisionAmount("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleFinalizeRevision() {
    if (!pendingRevision) return;
    try {
      await finalizeRevision.mutateAsync(pendingRevision.id);
      toast.success("Revision finalized and applied to the budget.");
      setPendingRevision(null);
    } catch (err) {
      // Real backend behavior: if a Workflow Engine chain governs
      // budget revisions for this tenant, this 409s with the exact
      // workflow-instance endpoint to approve through instead (see
      // finalize_budget_revision in services.py) -- surfaced verbatim.
      toast.error(getErrorMessage(err));
    }
  }

  if (cbs.isLoading) return <LoadingState variant="detail" label="Loading cost breakdown structure" />;
  if (!cbs.data) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <Badge tone={cbs.data.is_approved ? "green" : "amber"}>{cbs.data.is_approved ? "Approved baseline" : "Pending approval"}</Badge>
        {!cbs.data.is_approved && (
          <Button variant="secondary" onClick={handleApprove} disabled={approve.isPending}>
            Approve baseline
          </Button>
        )}
      </div>
      <Table ariaLabel="Cost breakdown structure line items">
        <thead>
          <tr>
            <Th>Description</Th>
            <Th>Qty</Th>
            <Th>Unit rate</Th>
            <Th>Budgeted amount</Th>
            <Th />
          </tr>
        </thead>
        <tbody>
          {cbs.data.line_items.map((li) => (
            <Fragment key={li.id}>
              <tr>
                <Td>{li.description}</Td>
                <Td mono>
                  {li.quantity} {li.unit}
                </Td>
                <Td mono>{li.unit_rate}</Td>
                <Td mono>{li.budgeted_amount}</Td>
                <Td style={{ textAlign: "right" }}>
                  {cbs.data.is_approved && (
                    <Button variant="ghost" onClick={() => setRevisingLineId(revisingLineId === li.id ? null : li.id)}>
                      {revisingLineId === li.id ? "Cancel" : "Revise →"}
                    </Button>
                  )}
                </Td>
              </tr>
              {revisingLineId === li.id && (
                <tr>
                  <td colSpan={5} style={{ background: "var(--sf-paper-dim)", padding: 12 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                      <Field label="Reason" required>
                        <Input value={revisionReason} onChange={(e) => setRevisionReason(e.target.value)} />
                      </Field>
                      <Field label="Revised amount" required>
                        <Input value={revisionAmount} onChange={(e) => setRevisionAmount(e.target.value)} />
                      </Field>
                      <Button variant="secondary" onClick={() => handleCreateRevision(li.id)} disabled={createRevision.isPending}>
                        Submit revision
                      </Button>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </Table>
      <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 8 }}>
        A pending revision is applied by finalizing it once its workflow reports approved — if a rejection happens
        upstream, finalizing will surface that as an error here rather than silently applying it.
      </p>
      {pendingRevision && (
        <div style={{ marginTop: 12, padding: 12, background: "var(--sf-amber-dim)", borderRadius: "var(--sf-radius)", fontSize: 13 }}>
          <div style={{ marginBottom: 8 }}>A revision on this CBS is pending — finalize it once its governing workflow (if any) has approved it.</div>
          <Button variant="secondary" onClick={handleFinalizeRevision} disabled={finalizeRevision.isPending}>
            {finalizeRevision.isPending ? "Finalizing…" : "Finalize revision"}
          </Button>
        </div>
      )}
    </div>
  );
}

// --- Main workspace ----------------------------------------------------------

export default function EstimatePage() {
  const { tenderId } = useParams();
  const { data: versions, isLoading: versionsLoading } = useEstimateVersions(tenderId);
  const createVersion = useCreateEstimateVersion(tenderId);
  const toast = useToast();

  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const currentVersion = versions?.find((v) => v.id === selectedVersionId) ?? versions?.find((v) => v.status !== "superseded") ?? versions?.[0];
  const versionId = currentVersion?.id;

  const submitVersion = useSubmitEstimateVersion(versionId, tenderId);
  const { data: boqItems } = useBOQItems(versionId);
  const addBOQItem = useAddBOQItem(versionId);
  const engineersEstimate = useEngineersEstimate(versionId);
  const tenderPrice = useTenderPrice(versionId);
  const addMarkup = useAddMarkup(versionId);
  const addContingency = useAddContingencyItem(versionId);
  const generateCBS = useGenerateCBS(versionId);

  const [tab, setTab] = useState<Tab>("boq");
  const [pricingItemId, setPricingItemId] = useState<string | null>(null);
  const [itemDescription, setItemDescription] = useState("");
  const [itemUnit, setItemUnit] = useState("");
  const [itemQty, setItemQty] = useState("");

  const [sessionMarkups, setSessionMarkups] = useState<Markup[]>([]);
  const [markupForm, setMarkupForm] = useState({ scope: "whole_tender", overhead_pct: "5", profit_pct: "8" });
  const [sessionContingency, setSessionContingency] = useState<ContingencyItem[]>([]);
  const [contingencyForm, setContingencyForm] = useState({ kind: "contingency", basis: "percentage", value: "5", description: "" });

  const [cbsId, setCbsId] = useState<string | null>(null);

  async function handleCreateVersion() {
    try {
      const res = await createVersion.mutateAsync("What-if version");
      toast.success(`Version ${res.data.version_number} created.`);
      setSelectedVersionId(res.data.id);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleAddItem(e: React.FormEvent) {
    e.preventDefault();
    try {
      await addBOQItem.mutateAsync({ description: itemDescription, unit: itemUnit || undefined, quantity: itemQty || undefined });
      setItemDescription("");
      setItemUnit("");
      setItemQty("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleSubmitVersion() {
    if (!window.confirm("Submit this estimate version? It becomes the tender's priced estimate and locks the linked tender's BOQ.")) return;
    try {
      await submitVersion.mutateAsync();
      toast.success("Estimate version submitted.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleAddMarkup(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await addMarkup.mutateAsync(markupForm);
      setSessionMarkups((prev) => [...prev, res.data]);
      toast.success("Markup record saved.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleAddContingency(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await addContingency.mutateAsync(contingencyForm);
      setSessionContingency((prev) => [...prev, res.data]);
      toast.success("Contingency item added — reflected in the tender price total.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleGenerateCBS() {
    try {
      const res = await generateCBS.mutateAsync(undefined);
      setCbsId(res.data.id);
      setTab("cbs");
      toast.success("Cost Breakdown Structure generated.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  if (versionsLoading) {
    return (
      <div>
        <PageHeader eyebrow="Estimating" title="Estimate" />
        <LoadingState variant="detail" label="Loading estimate" />
      </div>
    );
  }

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

  if (!currentVersion || !versionId) return null;

  const directCost = engineersEstimate.data ? Number(engineersEstimate.data.cost_only_total) : null;
  const itemsTotal = tenderPrice.data ? Number(tenderPrice.data.items_total) : null;
  // Aggregate markup baked into unit rates = items_total (which
  // includes each item's per-item markup) minus the pure cost-only
  // total -- both real backend totals, simple subtraction, no
  // reinvented calculation.
  const aggregateMarkup = directCost !== null && itemsTotal !== null ? itemsTotal - directCost : null;

  return (
    <div>
      <PageHeader
        eyebrow="Estimating"
        title={`Estimate — ${currentVersion.label || `v${currentVersion.version_number}`}`}
        action={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Select value={versionId} onChange={(e) => setSelectedVersionId(e.target.value)} aria-label="Select estimate version" style={{ width: 180 }}>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version_number} {v.label ? `— ${v.label}` : ""} ({v.status})
                </option>
              ))}
            </Select>
            <Button variant="ghost" onClick={handleCreateVersion} disabled={createVersion.isPending}>
              + What-if version
            </Button>
            <Badge tone={currentVersion.status === "submitted" ? "green" : currentVersion.status === "superseded" ? "neutral" : "amber"}>
              {currentVersion.status}
            </Badge>
          </div>
        }
      />

      <div style={{ display: "flex", gap: 4, marginBottom: 20, borderBottom: "1px solid var(--sf-line)" }}>
        {(["boq", "breakdown", "resources", "cbs"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "10px 16px",
              background: "none",
              border: "none",
              borderBottom: tab === t ? "2px solid var(--sf-navy-900)" : "2px solid transparent",
              fontWeight: tab === t ? 700 : 500,
              fontSize: 13,
              cursor: "pointer",
              color: tab === t ? "var(--sf-navy-900)" : "var(--sf-navy-400)",
              textTransform: "capitalize",
            }}
          >
            {t === "boq" ? "BOQ & pricing" : t === "breakdown" ? "Cost breakdown" : t === "resources" ? "Resources" : "CBS & budget"}
          </button>
        ))}
      </div>

      {tab === "boq" && (
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Priced BOQ</h3>
          <form onSubmit={handleAddItem} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "3fr 1fr 1fr auto", gap: 8, marginBottom: 16 }}>
            <Input required placeholder="Description" value={itemDescription} onChange={(e) => setItemDescription(e.target.value)} />
            <Input placeholder="Unit" value={itemUnit} onChange={(e) => setItemUnit(e.target.value)} />
            <Input placeholder="Qty" value={itemQty} onChange={(e) => setItemQty(e.target.value)} />
            <Button type="submit" variant="secondary" disabled={addBOQItem.isPending}>
              Add
            </Button>
          </form>

          {boqItems?.length ? (
            <Table ariaLabel="Priced BOQ items">
              <thead>
                <tr>
                  <Th>Description</Th>
                  <Th>Qty</Th>
                  <Th>Unit rate</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {boqItems.map((item) => (
                  <Fragment key={item.id}>
                    <tr>
                      <Td>{item.description}</Td>
                      <Td mono>
                        {item.quantity || "—"} {item.unit}
                      </Td>
                      <Td mono>{item.unit_rate ? formatMoney(item.unit_rate) : "Not priced"}</Td>
                      <Td style={{ textAlign: "right" }}>
                        <Button variant="ghost" onClick={() => setPricingItemId(pricingItemId === item.id ? null : item.id)}>
                          {pricingItemId === item.id ? "Close" : "Price →"}
                        </Button>
                      </Td>
                    </tr>
                    {pricingItemId === item.id && (
                      <tr>
                        <td colSpan={4} style={{ borderBottom: "1px solid var(--sf-line)", background: "var(--sf-paper-dim)" }}>
                          <RateAnalysisRow item={item} versionId={versionId} onSaved={() => setPricingItemId(null)} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </Table>
          ) : (
            <EmptyState title="No BOQ items yet" hint="Add a line item above, or pull them from the tender's own BOQ (Tender detail page)." />
          )}
        </Card>
      )}

      {tab === "breakdown" && (
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
          <div>
            <Card style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Cost breakdown</h3>
              <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 12 }}>
                Direct cost and grand total come straight from the backend's Engineer's Estimate and Tender Price
                endpoints. Markup here is the difference between them — both real numbers, just subtracted — because
                the backend doesn't expose an aggregate markup figure directly (it's baked into each item's unit rate
                at save time). This deployment has no distinct "indirect cost" concept in the estimating backend;
                Contingency/Risk Allowance below is the closest thing it tracks.
              </p>
              <div style={{ fontSize: 13 }}>
                <Row label="Direct cost" value={directCost} />
                <Row label="Markup (derived)" value={aggregateMarkup} />
                <Row label="Contingency / risk allowance" value={tenderPrice.data ? Number(tenderPrice.data.contingency_total) : null} />
                <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700, borderTop: "1px solid var(--sf-line)", paddingTop: 8, marginTop: 8 }}>
                  <span>Total estimate</span>
                  <span className="sf-mono">{tenderPrice.data ? formatMoney(tenderPrice.data.grand_total) : "—"}</span>
                </div>
              </div>
            </Card>

            <Card style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 4 }}>Whole-tender / section / item markup records</h3>
              <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 12 }}>
                <strong>Backend gap:</strong> these records are stored but not currently applied to the Total Estimate
                above by the backend — the markup that actually affects totals is the per-item markup % entered when
                pricing each BOQ item. There's also no list endpoint for these, so only what you add this session is
                shown below.
              </p>
              <form onSubmit={handleAddMarkup} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 8, marginBottom: 12 }}>
                <Select value={markupForm.scope} onChange={(e) => setMarkupForm({ ...markupForm, scope: e.target.value })}>
                  <option value="whole_tender">Whole tender</option>
                  <option value="section">Section</option>
                  <option value="item">Item</option>
                </Select>
                <Input placeholder="Overhead %" value={markupForm.overhead_pct} onChange={(e) => setMarkupForm({ ...markupForm, overhead_pct: e.target.value })} />
                <Input placeholder="Profit %" value={markupForm.profit_pct} onChange={(e) => setMarkupForm({ ...markupForm, profit_pct: e.target.value })} />
                <Button type="submit" variant="secondary" disabled={addMarkup.isPending}>
                  Add
                </Button>
              </form>
              {sessionMarkups.map((m) => (
                <div key={m.id} style={{ fontSize: 12, padding: "4px 0" }}>
                  {m.scope} — overhead {m.overhead_pct}%, profit {m.profit_pct}%
                </div>
              ))}
            </Card>

            <Card>
              <h3 style={{ fontSize: 14, marginBottom: 4 }}>Contingency / risk allowance</h3>
              <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 12 }}>
                Unlike markup records above, these <em>are</em> included in the Total Estimate immediately. No list
                endpoint exists here either, so only this session's additions are shown.
              </p>
              <form onSubmit={handleAddContingency} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 2fr auto", gap: 8, marginBottom: 12 }}>
                <Select value={contingencyForm.kind} onChange={(e) => setContingencyForm({ ...contingencyForm, kind: e.target.value })}>
                  <option value="contingency">Contingency</option>
                  <option value="risk_allowance">Risk allowance</option>
                </Select>
                <Select value={contingencyForm.basis} onChange={(e) => setContingencyForm({ ...contingencyForm, basis: e.target.value })}>
                  <option value="percentage">% of items total</option>
                  <option value="fixed">Fixed amount</option>
                </Select>
                <Input placeholder="Value" value={contingencyForm.value} onChange={(e) => setContingencyForm({ ...contingencyForm, value: e.target.value })} />
                <Input placeholder="Description (optional)" value={contingencyForm.description} onChange={(e) => setContingencyForm({ ...contingencyForm, description: e.target.value })} />
                <Button type="submit" variant="secondary" disabled={addContingency.isPending}>
                  Add
                </Button>
              </form>
              {sessionContingency.map((c) => (
                <div key={c.id} style={{ fontSize: 12, padding: "4px 0" }}>
                  {c.kind} — {c.basis === "percentage" ? `${c.value}%` : formatMoney(c.value)}
                  {c.description ? ` — ${c.description}` : ""}
                </div>
              ))}
            </Card>
          </div>

          <div>
            <Card>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Version &amp; award</h3>
              {currentVersion.status !== "submitted" ? (
                <Button style={{ width: "100%" }} onClick={handleSubmitVersion} disabled={submitVersion.isPending}>
                  Submit estimate version
                </Button>
              ) : (
                <>
                  <Badge tone="green">Submitted — estimate locked</Badge>
                  {!cbsId && (
                    <Button style={{ width: "100%", marginTop: 12 }} variant="secondary" onClick={handleGenerateCBS} disabled={generateCBS.isPending}>
                      Generate Cost Breakdown Structure
                    </Button>
                  )}
                  {cbsId && (
                    <Button style={{ width: "100%", marginTop: 12 }} variant="ghost" onClick={() => setTab("cbs")}>
                      View CBS →
                    </Button>
                  )}
                </>
              )}
            </Card>
          </div>
        </div>
      )}

      {tab === "resources" && (
        <div>
          <ResourceSubTabs />
        </div>
      )}

      {tab === "cbs" && (
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Cost Breakdown Structure</h3>
          {cbsId ? (
            <CBSPanel cbsId={cbsId} />
          ) : (
            <EmptyState
              title="No CBS generated yet"
              hint="Submit this estimate version, then generate the Cost Breakdown Structure from the Cost breakdown tab."
            />
          )}
        </Card>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: number | null }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
      <span>{label}</span>
      <span className="sf-mono">{value === null ? "—" : formatMoney(value)}</span>
    </div>
  );
}

function ResourceSubTabs() {
  const [sub, setSub] = useState<"cost_library" | "materials" | "equipment" | "labor">("cost_library");
  return (
    <Card>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {(
          [
            ["cost_library", "Cost library"],
            ["materials", "Material prices"],
            ["equipment", "Equipment rates"],
            ["labor", "Labor rates"],
          ] as [typeof sub, string][]
        ).map(([key, label]) => (
          <Button key={key} variant={sub === key ? "secondary" : "ghost"} onClick={() => setSub(key)}>
            {label}
          </Button>
        ))}
      </div>
      {sub === "cost_library" && <CostLibraryTab />}
      {sub === "materials" && <MaterialPricesTab />}
      {sub === "equipment" && <EquipmentRatesTab />}
      {sub === "labor" && <LaborRatesTab />}
    </Card>
  );
}
