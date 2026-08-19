import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input } from "../../components/ui";
import {
  useEquipment,
  useMaintenanceRecords,
  useCreateMaintenanceRecord,
  useEquipmentAvailability,
  useEquipmentCostPerHour,
  useAddUtilizationRecord,
} from "./hooks";

export default function EquipmentDetailPage() {
  const { equipmentId } = useParams();
  const { data: equipment, isLoading } = useEquipment(equipmentId);
  const { data: maintenance } = useMaintenanceRecords(equipmentId);
  const { data: availability } = useEquipmentAvailability(equipmentId);
  const { data: costPerHour } = useEquipmentCostPerHour(equipmentId);

  const createMaintenance = useCreateMaintenanceRecord(equipmentId);
  const [maintDesc, setMaintDesc] = useState("");

  const addUtilization = useAddUtilizationRecord(equipmentId);
  const [utilForm, setUtilForm] = useState({ record_date: "", hours_scheduled: "", hours_operated: "" });

  if (isLoading || !equipment) return <p>Loading…</p>;

  async function handleAddMaintenance(e: React.FormEvent) {
    e.preventDefault();
    await createMaintenance.mutateAsync({ description: maintDesc });
    setMaintDesc("");
  }

  async function handleAddUtilization(e: React.FormEvent) {
    e.preventDefault();
    await addUtilization.mutateAsync(utilForm);
    setUtilForm({ record_date: "", hours_scheduled: "", hours_operated: "" });
  }

  return (
    <div>
      <PageHeader eyebrow="Equipment" title={equipment.name} action={<Badge tone="neutral">{equipment.status}</Badge>} />

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20 }}>
        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Maintenance records</h3>
            {maintenance?.length ? (
              <Table>
                <thead><tr><Th>Type</Th><Th>Description</Th><Th>Status</Th></tr></thead>
                <tbody>
                  {maintenance.map((m: any) => (
                    <tr key={m.id}>
                      <Td>{m.maintenance_type}</Td>
                      <Td>{m.description || "—"}</Td>
                      <Td><Badge tone={m.status === "completed" ? "green" : "amber"}>{m.status}</Badge></Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>No maintenance recorded yet.</p>
            )}
            <form onSubmit={handleAddMaintenance} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, marginTop: 12 }}>
              <Input placeholder="Description" value={maintDesc} onChange={(e) => setMaintDesc(e.target.value)} />
              <Button type="submit" disabled={createMaintenance.isPending}>Log</Button>
            </form>
          </Card>

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Record utilization</h3>
            <form onSubmit={handleAddUtilization} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 8 }}>
              <Input required type="date" value={utilForm.record_date} onChange={(e) => setUtilForm({ ...utilForm, record_date: e.target.value })} />
              <Input placeholder="Hours scheduled" value={utilForm.hours_scheduled} onChange={(e) => setUtilForm({ ...utilForm, hours_scheduled: e.target.value })} />
              <Input required placeholder="Hours operated" value={utilForm.hours_operated} onChange={(e) => setUtilForm({ ...utilForm, hours_operated: e.target.value })} />
              <Button type="submit" disabled={addUtilization.isPending}>Record</Button>
            </form>
          </Card>
        </div>

        <div>
          <Card style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>Details</h3>
            <div style={{ fontSize: 13, display: "grid", gap: 8 }}>
              <div><span style={{ color: "var(--sf-navy-400)" }}>Make / Model: </span>{[equipment.make, equipment.model].filter(Boolean).join(" / ") || "—"}</div>
              <div><span style={{ color: "var(--sf-navy-400)" }}>Ownership: </span>{equipment.ownership_type}</div>
              {equipment.acquisition_cost && <div><span style={{ color: "var(--sf-navy-400)" }}>Acquisition cost: </span><span className="sf-mono">{equipment.acquisition_cost}</span></div>}
            </div>
          </Card>

          {availability && (
            <Card style={{ marginBottom: 20 }}>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Availability</h3>
              <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{availability.availability_percentage ?? availability.percentage ?? "—"}%</div>
            </Card>
          )}

          {costPerHour && (
            <Card>
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>Cost per hour</h3>
              <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{costPerHour.cost_per_hour ?? "—"}</div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
