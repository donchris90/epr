import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { useWarehouses, useCreateWarehouse, useWarehouseStock, useMaterialItems, useCreateMaterialItem } from "./hooks";

const WAREHOUSE_TYPES = ["central_yard", "site_store", "quarry"];

export default function WarehousesPage() {
  const { data: warehouses, isLoading } = useWarehouses();
  const createWarehouse = useCreateWarehouse();
  const { data: materialItems } = useMaterialItems();
  const createMaterialItem = useCreateMaterialItem();

  const [showWhForm, setShowWhForm] = useState(false);
  const [whForm, setWhForm] = useState({ name: "", warehouse_type: "site_store", location: "" });

  const [showItemForm, setShowItemForm] = useState(false);
  const [itemForm, setItemForm] = useState({ code: "", description: "", unit: "" });

  const [selectedWarehouse, setSelectedWarehouse] = useState<string | null>(null);
  const { data: stock } = useWarehouseStock(selectedWarehouse || undefined);

  async function handleCreateWarehouse(e: React.FormEvent) {
    e.preventDefault();
    await createWarehouse.mutateAsync(whForm);
    setWhForm({ name: "", warehouse_type: "site_store", location: "" });
    setShowWhForm(false);
  }

  async function handleCreateItem(e: React.FormEvent) {
    e.preventDefault();
    await createMaterialItem.mutateAsync(itemForm);
    setItemForm({ code: "", description: "", unit: "" });
    setShowItemForm(false);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Inventory & Warehouse"
        title="Warehouses"
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="secondary" onClick={() => setShowItemForm((v) => !v)}>
              {showItemForm ? "Cancel" : "New material item"}
            </Button>
            <Button onClick={() => setShowWhForm((v) => !v)}>{showWhForm ? "Cancel" : "New warehouse"}</Button>
          </div>
        }
      />

      {showWhForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreateWarehouse} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 2fr auto", gap: 12 }}>
            <Field label="Name">
              <Input required value={whForm.name} onChange={(e) => setWhForm({ ...whForm, name: e.target.value })} />
            </Field>
            <Field label="Type">
              <select
                value={whForm.warehouse_type}
                onChange={(e) => setWhForm({ ...whForm, warehouse_type: e.target.value })}
                style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
              >
                {WAREHOUSE_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </Field>
            <Field label="Location (optional)">
              <Input value={whForm.location} onChange={(e) => setWhForm({ ...whForm, location: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createWarehouse.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {showItemForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreateItem} style={{ display: "grid", gridTemplateColumns: "1fr 2fr 1fr auto", gap: 12 }}>
            <Field label="Code">
              <Input required value={itemForm.code} onChange={(e) => setItemForm({ ...itemForm, code: e.target.value })} />
            </Field>
            <Field label="Description">
              <Input required value={itemForm.description} onChange={(e) => setItemForm({ ...itemForm, description: e.target.value })} />
            </Field>
            <Field label="Unit">
              <Input value={itemForm.unit} onChange={(e) => setItemForm({ ...itemForm, unit: e.target.value })} placeholder="bags, m3, tons" />
            </Field>
            <Button type="submit" disabled={createMaterialItem.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !warehouses?.length ? (
        <EmptyState title="No warehouses yet" hint="Create one to start receiving and issuing stock." />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 20 }}>
          <Card style={{ padding: 0 }}>
            <Table>
              <thead>
                <tr><Th>Name</Th><Th>Type</Th></tr>
              </thead>
              <tbody>
                {warehouses.map((w: any) => (
                  <tr
                    key={w.id}
                    onClick={() => setSelectedWarehouse(w.id)}
                    style={{ cursor: "pointer", background: selectedWarehouse === w.id ? "var(--sf-paper-dim)" : undefined }}
                  >
                    <Td>{w.name}</Td>
                    <Td><Badge tone="steel">{w.warehouse_type}</Badge></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>
              {selectedWarehouse ? "Stock on hand" : "Select a warehouse to view stock"}
            </h3>
            {selectedWarehouse && (
              stock?.length ? (
                <Table>
                  <thead>
                    <tr><Th>Material item</Th><Th>Qty on hand</Th><Th>Avg unit cost</Th></tr>
                  </thead>
                  <tbody>
                    {stock.map((s: any) => (
                      <tr key={s.id}>
                        <Td mono style={{ fontSize: 11 }}>{s.material_item_id.slice(0, 8)}…</Td>
                        <Td mono>{s.quantity_on_hand}</Td>
                        <Td mono>{s.average_unit_cost}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No stock recorded in this warehouse yet.</p>
              )
            )}
          </Card>
        </div>
      )}

      {materialItems?.length ? (
        <Card style={{ marginTop: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Material items</h3>
          <Table>
            <thead>
              <tr><Th>Code</Th><Th>Description</Th><Th>Unit</Th><Th>Tracking</Th></tr>
            </thead>
            <tbody>
              {materialItems.map((m: any) => (
                <tr key={m.id}>
                  <Td mono>{m.code}</Td>
                  <Td>{m.description}</Td>
                  <Td mono>{m.unit || "—"}</Td>
                  <Td>
                    {m.is_batch_tracked && <Badge tone="amber">Batch</Badge>}
                    {m.is_serial_tracked && <Badge tone="steel">Serial</Badge>}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      ) : null}
    </div>
  );
}
