import { useState } from "react";
import { Badge, Button, Card, ErrorBanner, Field, Input, Select } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useRegisterPortalUser, useSubcontractorOptions } from "./hooks";
import { useScpStore } from "./store";
import { useNavigate } from "react-router-dom";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function AccessPage() {
  const navigate = useNavigate();
  const session = useScpStore((s) => s.session);
  const setSession = useScpStore((s) => s.setSession);
  const { data: subcontractors, isLoading } = useSubcontractorOptions();
  const register = useRegisterPortalUser();

  const [subId, setSubId] = useState("");
  const [portalUserId, setPortalUserId] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  function openExisting(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!UUID_RE.test(portalUserId.trim())) return setError("Portal user ID must be a valid UUID.");
    if (!subId) return setError("Choose the subcontractor this portal user belongs to.");
    setSession({ id: portalUserId.trim(), subcontractor_id: subId });
    navigate("/subcontractor-portal");
  }

  async function registerNew(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!subId) return setError("Choose a subcontractor first.");
    try {
      const user = await register.mutateAsync({ subcontractor_id: subId, email: email.trim() });
      setSession({ id: user.id, subcontractor_id: user.subcontractor_id, email: user.email });
      navigate("/subcontractor-portal");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  const subName = subcontractors?.find((s) => s.id === session?.subcontractor_id)?.name;

  return (
    <div style={{ display: "grid", gap: 20, maxWidth: 720 }}>
      {error && <ErrorBanner title="Couldn't continue" detail={error} onDismiss={() => setError(null)} />}

      {session && (
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Current portal user</h3>
          <dl style={{ display: "grid", gridTemplateColumns: "140px 1fr", rowGap: 8, fontSize: 13, margin: 0 }}>
            <dt style={{ color: "var(--sf-navy-400)" }}>Email</dt>
            <dd style={{ margin: 0 }}>{session.email ?? "—"}</dd>
            <dt style={{ color: "var(--sf-navy-400)" }}>Subcontractor</dt>
            <dd style={{ margin: 0 }}>{subName ?? session.subcontractor_id}</dd>
            <dt style={{ color: "var(--sf-navy-400)" }}>Portal user ID</dt>
            <dd className="sf-mono" style={{ margin: 0, fontSize: 12 }}>{session.id}</dd>
            <dt style={{ color: "var(--sf-navy-400)" }}>Scope</dt>
            <dd style={{ margin: 0 }}><Badge tone="green">Own agreements only</Badge></dd>
          </dl>
        </Card>
      )}

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Register a portal user</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 14 }}>
          Creates a portal login scoped to exactly one subcontractor. Requires the <span className="sf-mono">scp:approve</span> permission.
        </p>
        <form onSubmit={registerNew}>
          <Field label="Subcontractor">
            <Select value={subId} onChange={(e) => setSubId(e.target.value)} required disabled={isLoading}>
              <option value="">{isLoading ? "Loading…" : "Select…"}</option>
              {subcontractors?.map((s) => (
                <option key={s.id} value={s.id}>{s.name}{s.trade_specialty ? ` — ${s.trade_specialty}` : ""}</option>
              ))}
            </Select>
          </Field>
          <Field label="Email">
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Button type="submit" disabled={register.isPending}>{register.isPending ? "Creating…" : "Create & open"}</Button>
        </form>
      </Card>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Open as an existing portal user</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 14 }}>
          Uses the subcontractor selected above. If the ID doesn't belong to that subcontractor, the server rejects every request.
        </p>
        <form onSubmit={openExisting}>
          <Field label="Portal user ID">
            <Input className="sf-mono" value={portalUserId} onChange={(e) => setPortalUserId(e.target.value)} placeholder="00000000-0000-0000-0000-000000000000" />
          </Field>
          <Button type="submit" variant="secondary">Open</Button>
        </form>
      </Card>
    </div>
  );
}
