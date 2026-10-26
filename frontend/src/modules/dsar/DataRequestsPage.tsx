import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../../api/client";
import { PageHeader, Card, Table, Th, Td, Badge, Button, Input, Select, Textarea, Field, ErrorBanner, EmptyState } from "../../components/ui";

export interface DsarRequest {
  id: string;
  request_type: string;
  subject_name: string;
  subject_email: string | null;
  subject_phone: string | null;
  details: string | null;
  status: "open" | "in_progress" | "completed" | "rejected";
  received_at: string;
  due_at: string;
  resolved_at: string | null;
  resolution_notes: string | null;
  actions: { table: string; id: string; action: string; at: string }[];
  is_overdue: boolean;
  source?: "staff" | "public";
  email_verified?: boolean;
  requester_notified_at?: string | null;
}

/** The tenant id from the signed-in session's token, for the public form link. */
function currentTenantId(): string | null {
  try {
    const t = localStorage.getItem("access_token");
    if (!t) return null;
    const payload = JSON.parse(atob(t.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.tenant_id ?? null;
  } catch {
    return null;
  }
}

interface SearchHit {
  id: string;
  table: string;
  summary: string;
}

const TYPES = ["access", "correction", "erasure", "restriction", "objection", "portability"];
// Must match backend app/dsar/services.py ERASABLE.
export const ERASABLE_TABLES = ["bdc_contacts", "wfm_casual_workers", "clp_portal_users", "vnp_portal_users", "scp_portal_users"];

function msg(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

const TONE: Record<string, "steel" | "green" | "brick" | "neutral"> = { open: "steel", in_progress: "steel", completed: "green", rejected: "neutral" };

/** Staff view of the Data Subject Request log (NDPA): log a request,
 * see its 30-day due date, search for the person's records, anonymise
 * them for erasure requests, and close the request with an outcome.
 * Backed by /v1/dsar/* (needs dsar:manage; search also dsar:search). */
export default function DataRequestsPage() {
  const [requests, setRequests] = useState<DsarRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const tenantId = currentTenantId();

  const load = useCallback(() => {
    apiClient
      .get("/dsar/requests")
      .then((res) => setRequests(res.data.data))
      .catch((e) => {
        setError(msg(e));
        setRequests([]);
      });
  }, []);

  useEffect(load, [load]);

  const selected = requests?.find((r) => r.id === selectedId) ?? null;

  return (
    <div>
      <PageHeader
        eyebrow="Compliance"
        title="Data Requests"
        action={<Button onClick={() => setShowNew((v) => !v)}>{showNew ? "Cancel" : "Log request"}</Button>}
      />
      {error && <ErrorBanner title={error} />}

      {tenantId && (
        <p style={{ fontSize: 12, color: "var(--sf-navy-600)", marginBottom: 12 }}>
          Public request form to share (e.g. in your privacy policy):{" "}
          <code data-testid="public-form-link">{`${window.location.origin}/privacy-request/${tenantId}`}</code>
        </p>
      )}

      {showNew && (
        <NewRequestForm
          onCreated={(r) => {
            setShowNew(false);
            setSelectedId(r.id);
            load();
          }}
        />
      )}

      {requests === null ? (
        <p style={{ fontSize: 13 }}>Loading…</p>
      ) : requests.length === 0 ? (
        <EmptyState title="No data requests logged" hint="Log a request when someone asks to access, correct or erase their personal data. A response is due within 30 days." />
      ) : (
        <Table ariaLabel="Data requests">
          <thead>
            <tr>
              <Th>Subject</Th>
              <Th>Type</Th>
              <Th>Status</Th>
              <Th>Due</Th>
            </tr>
          </thead>
          <tbody>
            {requests.map((r) => (
              <tr key={r.id} onClick={() => setSelectedId(r.id)} style={{ cursor: "pointer", background: r.id === selectedId ? "var(--sf-steel-dim)" : undefined }}>
                <Td>
                  {r.subject_name}{" "}
                  {r.source === "public" && <Badge tone={r.email_verified ? "green" : "neutral"}>{r.email_verified ? "Public · verified" : "Public · unverified"}</Badge>}
                </Td>
                <Td>{r.request_type}</Td>
                <Td>
                  <Badge tone={TONE[r.status] ?? "neutral"}>{r.status.replace("_", " ")}</Badge>
                </Td>
                <Td>
                  {new Date(r.due_at).toLocaleDateString()} {r.is_overdue && <Badge tone="brick">Overdue</Badge>}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}

      {selected && <RequestDetail key={selected.id} request={selected} onChanged={load} />}
    </div>
  );
}

function NewRequestForm({ onCreated }: { onCreated: (r: DsarRequest) => void }) {
  const [type, setType] = useState("access");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [details, setDetails] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.trim() && !phone.trim()) {
      setError("Enter an email or phone number so the person's records can be found.");
      return;
    }
    setSaving(true);
    try {
      const res = await apiClient.post("/dsar/requests", {
        request_type: type,
        subject_name: name.trim(),
        subject_email: email.trim() || null,
        subject_phone: phone.trim() || null,
        details: details.trim() || null,
      });
      onCreated(res.data);
    } catch (err) {
      setError(msg(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card style={{ marginBottom: 16 }}>
      <form onSubmit={submit}>
        <Field label="Request type">
          <Select value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Person's name">
          <Input required value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Email">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Phone">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </Field>
        <Field label="Details">
          <Textarea value={details} onChange={(e) => setDetails(e.target.value)} />
        </Field>
        {error && <ErrorBanner title={error} />}
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Log request"}
        </Button>
      </form>
    </Card>
  );
}

function RequestDetail({ request, onChanged }: { request: DsarRequest; onChanged: () => void }) {
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [notify, setNotify] = useState(true);
  const [notes, setNotes] = useState(request.resolution_notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const closed = request.status === "completed" || request.status === "rejected";

  const search = useCallback(() => {
    const params: Record<string, string> = {};
    if (request.subject_email) params.email = request.subject_email;
    if (request.subject_phone) params.phone = request.subject_phone;
    if (!params.email && !params.phone) {
      setHits([]);
      return;
    }
    apiClient
      .get("/dsar/search", { params })
      .then((res) => setHits(Object.values(res.data.results as Record<string, SearchHit[]>).flat()))
      .catch((e) => {
        setError(msg(e));
        setHits([]);
      });
  }, [request.subject_email, request.subject_phone]);

  useEffect(search, [search]);

  function toggle(id: string) {
    setPicked((p) => {
      const n = new Set(p);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
    setConfirming(false);
  }

  async function erase() {
    setError(null);
    try {
      await apiClient.post(`/dsar/requests/${request.id}/erase`, {
        records: (hits ?? []).filter((h) => picked.has(h.id)).map((h) => ({ table: h.table, id: h.id })),
      });
      setPicked(new Set());
      setConfirming(false);
      search();
      onChanged();
    } catch (err) {
      setError(msg(err));
    }
  }

  async function close(status: "completed" | "rejected") {
    setError(null);
    try {
      await apiClient.patch(`/dsar/requests/${request.id}`, { status, resolution_notes: notes || null, notify_requester: notify });
      onChanged();
    } catch (err) {
      setError(msg(err));
    }
  }

  const canErase = request.request_type === "erasure" && !closed;
  const canExport = (request.request_type === "access" || request.request_type === "portability") && !closed;
  const unverified = request.source === "public" && !request.email_verified;

  async function downloadExport() {
    setError(null);
    try {
      const res = await apiClient.get(`/dsar/requests/${request.id}/export`);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `data-export-${request.id}.json`;
      a.click();
      URL.revokeObjectURL(url);
      onChanged();
    } catch (err) {
      setError(msg(err));
    }
  }

  return (
    <Card style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600 }}>
        {request.request_type} request — {request.subject_name}
      </h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", margin: "4px 0 12px" }}>
        {[request.subject_email, request.subject_phone].filter(Boolean).join(" · ") || "No contact details"} · received{" "}
        {new Date(request.received_at).toLocaleDateString()} · due {new Date(request.due_at).toLocaleDateString()}
      </p>
      {request.details && <p style={{ fontSize: 13, marginBottom: 12 }}>{request.details}</p>}
      {unverified && (
        <p role="note" style={{ fontSize: 12, color: "var(--sf-brick)", marginBottom: 12 }}>
          Filed through the public form — the requester hasn't confirmed their email yet. Exporting or erasing their data is blocked until they do.
        </p>
      )}
      {error && <ErrorBanner title={error} />}

      <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Records found</h4>
      {hits === null ? (
        <p style={{ fontSize: 12 }}>Searching…</p>
      ) : hits.length === 0 ? (
        <p style={{ fontSize: 12, color: "var(--sf-navy-600)" }}>No matching records.</p>
      ) : (
        <div style={{ marginBottom: 12 }}>
          {hits.map((h) => {
            const erasable = canErase && ERASABLE_TABLES.includes(h.table);
            return (
              <label key={h.id} style={{ display: "flex", gap: 8, fontSize: 13, padding: "4px 0", opacity: erasable || !canErase ? 1 : 0.7 }}>
                {canErase && <input type="checkbox" disabled={!erasable} checked={picked.has(h.id)} onChange={() => toggle(h.id)} aria-label={h.summary} />}
                <span>{h.summary}</span>
                {canErase && !erasable && <span style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>handle manually</span>}
              </label>
            );
          })}
        </div>
      )}

      {canExport && (
        <Button variant="secondary" onClick={downloadExport} disabled={unverified} style={{ marginBottom: 12 }}>
          Download data export
        </Button>
      )}

      {canErase && picked.size > 0 &&
        (confirming ? (
          <div style={{ marginBottom: 12 }}>
            <span style={{ fontSize: 12, color: "var(--sf-brick)", marginRight: 8 }}>
              This anonymises {picked.size} record(s) and cannot be undone.
            </span>
            <Button variant="danger" onClick={erase}>
              Confirm erase
            </Button>{" "}
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button variant="danger" onClick={() => setConfirming(true)} style={{ marginBottom: 12 }}>
            Erase selected ({picked.size})
          </Button>
        ))}

      {request.actions.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Actions taken</h4>
          {request.actions.map((a, i) => (
            <div key={i} style={{ fontSize: 12, color: "var(--sf-navy-600)" }}>
              {new Date(a.at).toLocaleString()} —{" "}
              {a.action === "exported" ? "exported a copy of the person's data" : `${a.action} ${a.table} record`}
            </div>
          ))}
        </div>
      )}

      {closed ? (
        <p style={{ fontSize: 13 }}>
          <strong>{request.status}</strong>
          {request.resolution_notes ? ` — ${request.resolution_notes}` : ""}
          {request.requester_notified_at ? ` · requester emailed ${new Date(request.requester_notified_at).toLocaleDateString()}` : ""}
        </p>
      ) : (
        <div>
          <Field label="Outcome notes (required to reject)">
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
          {request.subject_email && (
            <label style={{ display: "flex", gap: 6, fontSize: 12, marginBottom: 8 }}>
              <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
              Email the requester the outcome
            </label>
          )}
          <Button onClick={() => close("completed")}>Mark completed</Button>{" "}
          <Button variant="secondary" onClick={() => close("rejected")}>
            Reject
          </Button>
        </div>
      )}
    </Card>
  );
}
