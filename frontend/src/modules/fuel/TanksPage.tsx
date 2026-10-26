import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useTanks, useCreateTank, useReconcileTank, useCreatePurchase, usePendingPurchases, useConfirmDelivery } from "./hooks";

export default function TanksPage() {
  const { data: tanks, isLoading } = useTanks();
  const createTank = useCreateTank();
  const reconcileTank = useReconcileTank();
  const createPurchase = useCreatePurchase();
  const { data: pending } = usePendingPurchases();
  const confirmDelivery = useConfirmDelivery();
  const [purchaseError, setPurchaseError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", tank_type: "bulk_storage", capacity_litres: "" });

  const [reconcileTankId, setReconcileTankId] = useState<string | null>(null);
  const [dipReading, setDipReading] = useState("");
  const [reconcileError, setReconcileError] = useState<string | null>(null);

  const [purchaseTankId, setPurchaseTankId] = useState<string | null>(null);
  const [purchaseForm, setPurchaseForm] = useState({ quantity_litres: "", unit_price: "" });
  const [alreadyDelivered, setAlreadyDelivered] = useState(true);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createTank.mutateAsync(form);
    setForm({ name: "", tank_type: "bulk_storage", capacity_litres: "" });
    setShowForm(false);
  }

  async function handleReconcile(e: React.FormEvent) {
    e.preventDefault();
    if (!reconcileTankId) return;
    setReconcileError(null);
    try {
      await reconcileTank.mutateAsync({ tankId: reconcileTankId, dip_reading_litres: dipReading });
      setDipReading("");
      setReconcileTankId(null);
    } catch (err) {
      setReconcileError(getErrorMessage(err));
    }
  }

  async function handlePurchase(e: React.FormEvent) {
    e.preventDefault();
    if (!purchaseTankId) return;
    setPurchaseError(null);
    try {
      await createPurchase.mutateAsync({ tank_id: purchaseTankId, ...purchaseForm, confirm_delivery: alreadyDelivered });
      setPurchaseForm({ quantity_litres: "", unit_price: "" });
      setPurchaseTankId(null);
    } catch (err) {
      setPurchaseError(getErrorMessage(err));
    }
  }

  async function handleConfirm(purchaseId: string) {
    setPurchaseError(null);
    try {
      await confirmDelivery.mutateAsync(purchaseId);
    } catch (err) {
      setPurchaseError(getErrorMessage(err));
    }
  }

  const tankName = (id: string) => tanks?.find((t: any) => t.id === id)?.name ?? "Unknown tank";

  return (
    <div>
      <PageHeader
        eyebrow="Fuel Management"
        title="Tanks"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New tank"}</Button>}
      />

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 12 }}>
            <Field label="Name">
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Type">
              <select
                value={form.tank_type}
                onChange={(e) => setForm({ ...form, tank_type: e.target.value })}
                style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
              >
                <option value="bulk_storage">Bulk storage</option>
                <option value="equipment_onboard">Equipment onboard</option>
              </select>
            </Field>
            <Field label="Capacity (litres)">
              <Input value={form.capacity_litres} onChange={(e) => setForm({ ...form, capacity_litres: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createTank.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {reconcileTankId && (
        <Card style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>Reconcile tank against dip reading</h3>
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
            A variance beyond tolerance is automatically flagged for review — the mechanism behind FUEL-08's theft
            detection.
          </p>
          {reconcileError && <ErrorBanner title="Reconciliation flagged a variance" detail={reconcileError} onDismiss={() => setReconcileError(null)} />}
          <form onSubmit={handleReconcile} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: 8 }}>
            <Input required placeholder="Dip reading (litres)" value={dipReading} onChange={(e) => setDipReading(e.target.value)} />
            <Button type="submit" disabled={reconcileTank.isPending}>Reconcile</Button>
            <Button type="button" variant="secondary" onClick={() => setReconcileTankId(null)}>Cancel</Button>
          </form>
        </Card>
      )}

      {purchaseTankId && (
        <Card style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Record fuel purchase</h3>
          <form onSubmit={handlePurchase} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto auto", gap: 8 }}>
            <Input required placeholder="Quantity (litres)" value={purchaseForm.quantity_litres} onChange={(e) => setPurchaseForm({ ...purchaseForm, quantity_litres: e.target.value })} />
            <Input required placeholder="Unit price" value={purchaseForm.unit_price} onChange={(e) => setPurchaseForm({ ...purchaseForm, unit_price: e.target.value })} />
            <Button type="submit" disabled={createPurchase.isPending}>Record</Button>
            <Button type="button" variant="secondary" onClick={() => setPurchaseTankId(null)}>Cancel</Button>
          </form>
          <label style={{ display: "flex", gap: 6, fontSize: 12, marginTop: 10 }}>
            <input type="checkbox" checked={alreadyDelivered} onChange={(e) => setAlreadyDelivered(e.target.checked)} />
            Fuel has already been delivered — add it to the tank now
          </label>
          {!alreadyDelivered && (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 6 }}>
              It will be listed under Pending deliveries and only added to the tank once you confirm delivery.
            </p>
          )}
        </Card>
      )}

      {purchaseError && <ErrorBanner title="Couldn't update fuel" detail={purchaseError} onDismiss={() => setPurchaseError(null)} />}

      {!!pending?.length && (
        <Card style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>Pending deliveries</h3>
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 10 }}>
            Recorded but not yet in the tank. Confirm each once the fuel has actually arrived.
          </p>
          <Table ariaLabel="Pending fuel deliveries">
            <thead><tr><Th>Tank</Th><Th>Quantity</Th><Th>Unit price</Th><Th></Th></tr></thead>
            <tbody>
              {pending.map((p) => (
                <tr key={p.id}>
                  <Td>{tankName(p.tank_id)}</Td>
                  <Td mono>{p.quantity_litres} L</Td>
                  <Td mono>{p.unit_price}</Td>
                  <Td>
                    <Button onClick={() => handleConfirm(p.id)} disabled={confirmDelivery.isPending}>
                      Confirm delivery
                    </Button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !tanks?.length ? (
        <EmptyState title="No fuel tanks registered" hint="Register a tank to start tracking purchases and issues." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr><Th>Name</Th><Th>Type</Th><Th>Current level</Th><Th></Th></tr>
            </thead>
            <tbody>
              {tanks.map((t: any) => (
                <tr key={t.id}>
                  <Td>{t.name}</Td>
                  <Td><Badge tone="neutral">{t.tank_type}</Badge></Td>
                  <Td mono>{t.current_level_litres} L</Td>
                  <Td>
                    <div style={{ display: "flex", gap: 10 }}>
                      <button onClick={() => setPurchaseTankId(t.id)} style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                        Purchase
                      </button>
                      <button onClick={() => setReconcileTankId(t.id)} style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                        Reconcile
                      </button>
                    </div>
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
