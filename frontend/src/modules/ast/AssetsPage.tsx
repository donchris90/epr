import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useAssets, useCreateAsset, useCreateDLP, useAddDefect, useResolveDefect, useVerifyDefect, useReleaseRetention } from "./hooks";

const ASSET_CATEGORIES = ["building", "road", "bridge", "drainage", "utility"];

export default function AssetsPage() {
  const { data: assets, isLoading } = useAssets();
  const createAsset = useCreateAsset();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", asset_category: "building" });

  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const createDLP = useCreateDLP(selectedAssetId || undefined);
  const [dlp, setDlp] = useState<any>(null);
  const addDefect = useAddDefect();
  const resolveDefect = useResolveDefect();
  const verifyDefect = useVerifyDefect();
  const releaseRetention = useReleaseRetention();
  const [defects, setDefects] = useState<any[]>([]);
  const [defectDesc, setDefectDesc] = useState("");
  const [releaseError, setReleaseError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    await createAsset.mutateAsync(form);
    setForm({ name: "", asset_category: "building" });
    setShowForm(false);
  }

  async function handleCreateDLP() {
    const res = await createDLP.mutateAsync({});
    setDlp(res.data);
    setDefects([]);
  }

  async function handleAddDefect(e: React.FormEvent) {
    e.preventDefault();
    const res = await addDefect.mutateAsync({ dlpId: dlp.id, description: defectDesc });
    setDefects((prev) => [...prev, res.data]);
    setDefectDesc("");
  }

  async function handleResolve(defectId: string) {
    const res = await resolveDefect.mutateAsync(defectId);
    setDefects((prev) => prev.map((d) => (d.id === defectId ? res.data : d)));
  }

  async function handleVerify(defectId: string) {
    const res = await verifyDefect.mutateAsync(defectId);
    setDefects((prev) => prev.map((d) => (d.id === defectId ? res.data : d)));
  }

  async function handleRelease() {
    setReleaseError(null);
    try {
      const res = await releaseRetention.mutateAsync(dlp.id);
      setDlp(res.data);
    } catch (err) {
      // Business rule: every defect must be status "verified" (not
      // just resolved) before retention can release.
      setReleaseError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Asset Management"
        title="Assets"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New asset"}</Button>}
      />

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 12 }}>
            <Field label="Name">
              <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Category">
              <select
                value={form.asset_category}
                onChange={(e) => setForm({ ...form, asset_category: e.target.value })}
                style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
              >
                {ASSET_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                ))}
              </select>
            </Field>
            <Button type="submit" disabled={createAsset.isPending} style={{ height: 38, alignSelf: "end" }}>Add</Button>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !assets?.length ? (
        <EmptyState title="No assets yet" hint="Assets are typically created from a locked as-built record at handover." />
      ) : (
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 20 }}>
          <Card style={{ padding: 0 }}>
            <Table>
              <thead><tr><Th>Name</Th><Th>Category</Th></tr></thead>
              <tbody>
                {assets.map((a: any) => (
                  <tr
                    key={a.id}
                    onClick={() => { setSelectedAssetId(a.id); setDlp(null); setDefects([]); }}
                    style={{ cursor: "pointer", background: selectedAssetId === a.id ? "var(--sf-paper-dim)" : undefined }}
                  >
                    <Td>{a.name}</Td>
                    <Td><Badge tone="neutral">{a.asset_category.replace(/_/g, " ")}</Badge></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>

          <Card>
            <h3 style={{ fontSize: 14, marginBottom: 4 }}>
              {selectedAssetId ? "Defects Liability Period" : "Select an asset"}
            </h3>
            {selectedAssetId && (
              <>
                <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
                  Retention releases only once every defect is verified — resolved alone isn't enough.
                </p>
                {!dlp ? (
                  <Button onClick={handleCreateDLP} disabled={createDLP.isPending}>Start DLP</Button>
                ) : (
                  <>
                    {releaseError && <ErrorBanner title="Cannot release retention" detail={releaseError} onDismiss={() => setReleaseError(null)} />}
                    <div style={{ marginBottom: 12 }}>
                      <Badge tone={dlp.retention_released ? "green" : "amber"}>{dlp.retention_released ? "Retention released" : "Retention held"}</Badge>
                    </div>
                    {defects.length > 0 && (
                      <Table>
                        <thead><tr><Th>Description</Th><Th>Status</Th><Th></Th></tr></thead>
                        <tbody>
                          {defects.map((d: any) => (
                            <tr key={d.id}>
                              <Td>{d.description}</Td>
                              <Td><Badge tone={d.status === "verified" ? "green" : d.status === "resolved" ? "amber" : "neutral"}>{d.status}</Badge></Td>
                              <Td>
                                <div style={{ display: "flex", gap: 8 }}>
                                  {d.status === "open" && (
                                    <button onClick={() => handleResolve(d.id)} style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Resolve</button>
                                  )}
                                  {d.status === "resolved" && (
                                    <button onClick={() => handleVerify(d.id)} style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Verify</button>
                                  )}
                                </div>
                              </Td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    )}
                    <form onSubmit={handleAddDefect} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, marginTop: 12, marginBottom: 12 }}>
                      <Input required placeholder="Defect description" value={defectDesc} onChange={(e) => setDefectDesc(e.target.value)} />
                      <Button type="submit" disabled={addDefect.isPending}>Add defect</Button>
                    </form>
                    {!dlp.retention_released && (
                      <Button variant="secondary" onClick={handleRelease} disabled={releaseRetention.isPending}>
                        {releaseRetention.isPending ? "Checking…" : "Release retention"}
                      </Button>
                    )}
                  </>
                )}
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
