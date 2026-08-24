import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Card, Button, Badge, Input, Field, Select } from "../../components/ui";
import { DataTable } from "../../components/DataTable";
import { QueryState } from "../../components/QueryState";
import { usePurchaseOrders, useCreatePurchaseOrder, useVendors } from "./hooks";
import type { PurchaseOrder, Vendor } from "./types";
import { useToast } from "../../lib/toast";
import { getErrorMessage, getFieldErrors } from "../../api/client";
import { useUnsavedChanges } from "../../lib/useUnsavedChanges";

const STATUS_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  draft: "neutral",
  pending_approval: "amber",
  approved: "steel",
  issued: "green",
  rejected: "brick",
};

export default function PurchaseOrdersPage() {
  const query = usePurchaseOrders();
  const { data: vendors } = useVendors();
  const createPO = useCreatePurchaseOrder();
  const toast = useToast();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ vendor_id: "", po_number: "", total_value: "" });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const isDirty = form.vendor_id !== "" || form.po_number !== "" || form.total_value !== "";
  useUnsavedChanges(isDirty && !createPO.isPending);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const errors: Record<string, string> = {};
    if (!form.vendor_id) errors.vendor_id = "Select a vendor.";
    if (!form.po_number.trim()) errors.po_number = "PO number is required.";
    if (!form.total_value.trim()) errors.total_value = "Total value is required.";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setFormError(null);
    try {
      await createPO.mutateAsync({ vendor_id: form.vendor_id, po_number: form.po_number, total_value: form.total_value });
      toast.success(`Purchase order "${form.po_number}" was created.`);
      setForm({ vendor_id: "", po_number: "", total_value: "" });
      setShowForm(false);
    } catch (err) {
      setFieldErrors(Object.fromEntries(getFieldErrors(err).map((f) => [f.field, f.message])));
      setFormError(getErrorMessage(err));
    }
  }

  function cancelForm() {
    if (isDirty && !window.confirm("Discard unsaved changes?")) return;
    setForm({ vendor_id: "", po_number: "", total_value: "" });
    setFieldErrors({});
    setFormError(null);
    setShowForm(false);
  }

  const vendorsById: Record<string, Vendor> = Object.fromEntries((vendors ?? []).map((v) => [v.id, v]));

  const columns = useMemo(
    () => [
      { key: "po_number", header: "PO number", render: (po: PurchaseOrder) => <span className="sf-mono">{po.po_number}</span>, sortValue: (po: PurchaseOrder) => po.po_number },
      {
        key: "vendor",
        header: "Vendor",
        render: (po: PurchaseOrder) => vendorsById[po.vendor_id]?.name || po.vendor_id.slice(0, 8) + "…",
        sortValue: (po: PurchaseOrder) => vendorsById[po.vendor_id]?.name ?? po.vendor_id,
      },
      {
        key: "total",
        header: "Total value",
        render: (po: PurchaseOrder) => (
          <span className="sf-mono">
            {po.currency} {po.total_value}
          </span>
        ),
        sortValue: (po: PurchaseOrder) => Number(po.total_value) || 0,
        align: "right" as const,
      },
      {
        key: "status",
        header: "Status",
        render: (po: PurchaseOrder) => <Badge tone={STATUS_TONE[po.status] ?? "neutral"}>{po.status.replace(/_/g, " ")}</Badge>,
        sortValue: (po: PurchaseOrder) => po.status,
      },
    ],
    [vendorsById]
  );

  return (
    <div>
      <PageHeader
        eyebrow="Procurement"
        title="Purchase Orders"
        action={<Button onClick={() => (showForm ? cancelForm() : setShowForm(true))}>{showForm ? "Cancel" : "New PO"}</Button>}
      />

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate} noValidate>
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 16 }}>
              <Field label="Vendor" required error={fieldErrors.vendor_id}>
                <Select value={form.vendor_id} onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}>
                  <option value="">Select…</option>
                  {(vendors ?? []).map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="PO number" required error={fieldErrors.po_number}>
                <Input value={form.po_number} onChange={(e) => setForm({ ...form, po_number: e.target.value })} />
              </Field>
              <Field label="Total value" required error={fieldErrors.total_value}>
                <Input value={form.total_value} onChange={(e) => setForm({ ...form, total_value: e.target.value })} />
              </Field>
            </div>
            {formError && (
              <div role="alert" style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>
                {formError}
              </div>
            )}
            <Button type="submit" disabled={createPO.isPending}>
              {createPO.isPending ? "Saving…" : "Save purchase order"}
            </Button>
          </form>
        </Card>
      )}

      <Card style={{ padding: query.isLoading || query.isError ? 0 : undefined }}>
        <QueryState
          query={query}
          variant="table"
          loadingLabel="Loading purchase orders"
          emptyTitle="No purchase orders yet"
          emptyHint="Create one directly, or from an approved purchase request."
          emptyAction={<Button onClick={() => setShowForm(true)}>New PO</Button>}
        >
          {(pos: PurchaseOrder[]) => (
            <DataTable
              columns={columns}
              rows={pos}
              getRowId={(po) => po.id}
              exportFilename="purchase-orders"
              searchFields={(po) => [po.po_number, vendorsById[po.vendor_id]?.name, po.status]}
              searchPlaceholder="Search purchase orders…"
              emptyTitle="No purchase orders match your search"
              rowActions={(po) => (
                <Link to={`orders/${po.id}`} style={{ fontSize: 12, fontWeight: 600 }}>
                  Open →
                </Link>
              )}
            />
          )}
        </QueryState>
      </Card>
    </div>
  );
}
