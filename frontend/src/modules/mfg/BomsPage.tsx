import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, EmptyState, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useMaterialItems } from "../inv/hooks";
import { useBoms, useCreateBom } from "./hooks";

const selectStyle = { padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" };
const emptyLine = { component_item_id: "", quantity: "", scrap_percent: "0" };

export default function BomsPage() {
  const { data: boms, isLoading } = useBoms();
  const { data: items } = useMaterialItems();
  const create = useCreateBom();
  const [show, setShow] = useState(false);
  const [head, setHead] = useState({ code: "", name: "", product_item_id: "", output_quantity: "1" });
  const [lines, setLines] = useState([{ ...emptyLine }]);
  const [error, setError] = useState<string | null>(null);

  const itemLabel = (id: string) => items?.find((i) => i.id === id)?.code ?? "Unknown item";
  const setLine = (idx: number, patch: Partial<typeof emptyLine>) =>
    setLines((ls) => ls.map((l, i) => (i === idx ? { ...l, ...patch } : l)));

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({ ...head, lines });
      setHead({ code: "", name: "", product_item_id: "", output_quantity: "1" });
      setLines([{ ...emptyLine }]);
      setShow(false);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Manufacturing"
        title="Bills of materials"
        action={<Button onClick={() => setShow((v) => !v)}>{show ? "Cancel" : "New BOM"}</Button>}
      />
      {error && <ErrorBanner title="Couldn't save BOM" detail={error} onDismiss={() => setError(null)} />}

      {show && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr 2fr 1fr", gap: 12, marginBottom: 12 }}>
              <Field label="Code">
                <Input required value={head.code} onChange={(e) => setHead({ ...head, code: e.target.value })} />
              </Field>
              <Field label="Name">
                <Input required value={head.name} onChange={(e) => setHead({ ...head, name: e.target.value })} />
              </Field>
              <Field label="Product made">
                <select required value={head.product_item_id} onChange={(e) => setHead({ ...head, product_item_id: e.target.value })} style={selectStyle}>
                  <option value="">Select item…</option>
                  {items?.map((i) => (
                    <option key={i.id} value={i.id}>{i.code} — {i.description}</option>
                  ))}
                </select>
              </Field>
              <Field label="Makes (quantity)">
                <Input required inputMode="decimal" value={head.output_quantity} onChange={(e) => setHead({ ...head, output_quantity: e.target.value })} />
              </Field>
            </div>

            <h3 style={{ fontSize: 13, marginBottom: 8 }}>Components (for the quantity above)</h3>
            {lines.map((line, idx) => (
              <div key={idx} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "3fr 1fr 1fr auto", gap: 8, marginBottom: 8 }}>
                <select
                  required
                  aria-label={`Component ${idx + 1}`}
                  value={line.component_item_id}
                  onChange={(e) => setLine(idx, { component_item_id: e.target.value })}
                  style={selectStyle}
                >
                  <option value="">Select component…</option>
                  {items?.map((i) => (
                    <option key={i.id} value={i.id}>{i.code} — {i.description}</option>
                  ))}
                </select>
                <Input required inputMode="decimal" aria-label={`Quantity ${idx + 1}`} placeholder="Quantity" value={line.quantity} onChange={(e) => setLine(idx, { quantity: e.target.value })} />
                <Input inputMode="decimal" aria-label={`Scrap % ${idx + 1}`} placeholder="Scrap %" value={line.scrap_percent} onChange={(e) => setLine(idx, { scrap_percent: e.target.value })} />
                <Button type="button" variant="ghost" disabled={lines.length === 1} onClick={() => setLines((ls) => ls.filter((_, i) => i !== idx))}>
                  Remove
                </Button>
              </div>
            ))}
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <Button type="button" variant="secondary" onClick={() => setLines((ls) => [...ls, { ...emptyLine }])}>Add component</Button>
              <Button type="submit" disabled={create.isPending}>Save BOM</Button>
            </div>
          </form>
        </Card>
      )}

      {isLoading ? null : !boms?.length ? (
        <EmptyState title="No bills of materials yet" hint="A BOM says what a product is made from. Add your raw materials as items first, then build the recipe here." />
      ) : (
        <Card>
          <Table ariaLabel="Bills of materials">
            <thead>
              <tr><Th>Code</Th><Th>Name</Th><Th>Product</Th><Th>Makes</Th><Th>Components</Th></tr>
            </thead>
            <tbody>
              {boms.map((b) => (
                <tr key={b.id}>
                  <Td mono>{b.code}</Td>
                  <Td>{b.name}</Td>
                  <Td mono>{itemLabel(b.product_item_id)}</Td>
                  <Td mono>{Number(b.output_quantity)}</Td>
                  <Td>
                    {b.lines.map((l) => `${itemLabel(l.component_item_id)} × ${Number(l.quantity)}${Number(l.scrap_percent) ? ` (+${Number(l.scrap_percent)}%)` : ""}`).join(", ")}
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
