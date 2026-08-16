import { useState } from "react";
import { PageHeader, Card, Button, Badge, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import {
  useCreateDesignSurface,
  useApproveDesignSurface,
  useCreateEarthworksVolume,
  useSubmitEarthworksForBilling,
  useCreateAsBuiltRecord,
  useLockAsBuiltRecord,
} from "./hooks";

export default function SurveyPage() {
  const createSurface = useCreateDesignSurface();
  const approveSurface = useApproveDesignSurface();
  const [surfaceForm, setSurfaceForm] = useState({ project_id: "", name: "" });
  const [surface, setSurface] = useState<any>(null);

  const createVolume = useCreateEarthworksVolume();
  const submitVolume = useSubmitEarthworksForBilling();
  const [volumeForm, setVolumeForm] = useState({ cut_volume: "", fill_volume: "" });
  const [volume, setVolume] = useState<any>(null);
  const [volumeError, setVolumeError] = useState<string | null>(null);

  const createAsBuilt = useCreateAsBuiltRecord();
  const lockAsBuilt = useLockAsBuiltRecord();
  const [asBuiltForm, setAsBuiltForm] = useState({ scope_reference: "", constructed_level: "" });
  const [asBuilt, setAsBuilt] = useState<any>(null);

  async function handleCreateSurface(e: React.FormEvent) {
    e.preventDefault();
    const res = await createSurface.mutateAsync(surfaceForm);
    setSurface(res.data);
  }

  async function handleApproveSurface() {
    await approveSurface.mutateAsync(surface.id);
    setSurface({ ...surface, is_approved: true });
  }

  async function handleCreateVolume(e: React.FormEvent) {
    e.preventDefault();
    const res = await createVolume.mutateAsync({ project_id: surfaceForm.project_id, design_surface_id: surface?.id, ...volumeForm });
    setVolume(res.data);
  }

  async function handleSubmitVolume() {
    setVolumeError(null);
    try {
      const res = await submitVolume.mutateAsync(volume.id);
      setVolume(res.data);
    } catch (err) {
      // Business rule: only billable once the design surface it's
      // measured against is approved.
      setVolumeError(getErrorMessage(err));
    }
  }

  async function handleCreateAsBuilt(e: React.FormEvent) {
    e.preventDefault();
    const res = await createAsBuilt.mutateAsync({ project_id: surfaceForm.project_id, ...asBuiltForm });
    setAsBuilt(res.data);
  }

  async function handleLockAsBuilt() {
    const res = await lockAsBuilt.mutateAsync(asBuilt.id);
    setAsBuilt(res.data);
  }

  return (
    <div>
      <PageHeader eyebrow="Survey & Engineering" title="Design Surfaces, Earthworks & As-Builts" />

      <div style={{ marginBottom: 20, maxWidth: 320 }}>
        <Field label="Project ID (used for everything below)">
          <Input required value={surfaceForm.project_id} onChange={(e) => setSurfaceForm({ ...surfaceForm, project_id: e.target.value })} />
        </Field>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20 }}>
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Design surface</h3>
          <form onSubmit={handleCreateSurface} style={{ marginBottom: 12 }}>
            <Field label="Name">
              <Input required value={surfaceForm.name} onChange={(e) => setSurfaceForm({ ...surfaceForm, name: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createSurface.isPending || !surfaceForm.project_id}>Import</Button>
          </form>
          {surface && (
            <div style={{ fontSize: 13 }}>
              <div style={{ marginBottom: 8 }}>{surface.name}: <Badge tone={surface.is_approved ? "green" : "amber"}>{surface.is_approved ? "Approved" : "Pending approval"}</Badge></div>
              {!surface.is_approved && (
                <Button variant="secondary" onClick={handleApproveSurface} disabled={approveSurface.isPending}>Approve</Button>
              )}
            </div>
          )}
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>Earthworks volume</h3>
          <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 12 }}>Only billable once the design surface is approved.</p>
          {volumeError && <ErrorBanner title="Cannot submit for billing" detail={volumeError} onDismiss={() => setVolumeError(null)} />}
          <form onSubmit={handleCreateVolume} style={{ marginBottom: 12, display: "grid", gap: 8 }}>
            <Input placeholder="Cut volume" value={volumeForm.cut_volume} onChange={(e) => setVolumeForm({ ...volumeForm, cut_volume: e.target.value })} />
            <Input placeholder="Fill volume" value={volumeForm.fill_volume} onChange={(e) => setVolumeForm({ ...volumeForm, fill_volume: e.target.value })} />
            <Button type="submit" disabled={createVolume.isPending || !surfaceForm.project_id}>Calculate</Button>
          </form>
          {volume && (
            <div style={{ fontSize: 13 }}>
              <div style={{ marginBottom: 8 }}>
                <Badge tone={volume.submitted_for_billing ? "green" : "neutral"}>{volume.submitted_for_billing ? "Submitted for billing" : volume.status}</Badge>
              </div>
              {!volume.submitted_for_billing && (
                <Button variant="secondary" onClick={handleSubmitVolume} disabled={submitVolume.isPending}>Submit for billing</Button>
              )}
            </div>
          )}
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>As-built record</h3>
          <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 12 }}>Locking is one-way — there's no route back to editable.</p>
          <form onSubmit={handleCreateAsBuilt} style={{ marginBottom: 12, display: "grid", gap: 8 }}>
            <Input placeholder="Scope reference" value={asBuiltForm.scope_reference} onChange={(e) => setAsBuiltForm({ ...asBuiltForm, scope_reference: e.target.value })} />
            <Input placeholder="Constructed level" value={asBuiltForm.constructed_level} onChange={(e) => setAsBuiltForm({ ...asBuiltForm, constructed_level: e.target.value })} />
            <Button type="submit" disabled={createAsBuilt.isPending || !surfaceForm.project_id}>Record</Button>
          </form>
          {asBuilt && (
            <div style={{ fontSize: 13 }}>
              <div style={{ marginBottom: 8 }}>
                <Badge tone={asBuilt.locked ? "steel" : "amber"}>{asBuilt.locked ? "Locked" : "Editable"}</Badge>
              </div>
              {!asBuilt.locked && (
                <Button variant="secondary" onClick={handleLockAsBuilt} disabled={lockAsBuilt.isPending}>Lock</Button>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
