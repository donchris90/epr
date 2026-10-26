import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner, formatMoney } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useWorkCenters, useCreateWorkCenter } from "./hooks";

export default function WorkCentersPage() {
  const { data: centers, isLoading } = useWorkCenters();
  const create = useCreateWorkCenter();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", hourly_rate: "0" });
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync(form);
      setForm({ code: "", name: "", hourly_rate: "0" });
      setShow(false);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Manufacturing"
        title="Work centers"
        action={<Button onClick={() => setShow((v) => !v)}>{show ? "Cancel" : "New work center"}</Button>}
      />
      {error && <ErrorBanner title="Couldn't save work center" detail={error} onDismiss={() => setError(null)} />}
      {show && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr 1fr auto", gap: 12 }}>
            <Field label="Code">
              <Input required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </Field>
            <Field label="Name">
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Hourly rate (labour + overhead)">
              <Input required inputMode="decimal" value={form.hourly_rate} onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })} />
            </Field>
            <Button type="submit" disabled={create.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}
      {isLoading ? null : !centers?.length ? (
        <EmptyState title="No work centers yet" hint="A work center is a line, machine or station. Its hourly rate is what labour hours are costed at." />
      ) : (
        <Card>
          <Table ariaLabel="Work centers">
            <thead>
              <tr><Th>Code</Th><Th>Name</Th><Th>Hourly rate</Th><Th>Status</Th></tr>
            </thead>
            <tbody>
              {centers.map((c) => (
                <tr key={c.id}>
                  <Td mono>{c.code}</Td>
                  <Td>{c.name}</Td>
                  <Td mono>{formatMoney(c.hourly_rate)}</Td>
                  <Td>{c.is_active ? <Badge tone="green">Active</Badge> : <Badge>Inactive</Badge>}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
