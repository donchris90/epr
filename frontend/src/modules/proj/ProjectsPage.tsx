import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../../api/client";
import {
  PageHeader,
  Card,
  Button,
  Table,
  Th,
  Td,
  Badge,
  ErrorBanner,
  EmptyState,
  Input,
  Select,
  Field,
} from "../../components/ui";

interface Project {
  id: string;
  name: string;
  status: string;
  client_id: string | null;
  project_manager_id: string | null;
  start_date: string | null;
  end_date: string | null;
}

interface Company {
  id: string;
  name: string;
}

interface Client {
  id: string;
  name: string;
}

interface OrgUser {
  id: string;
  email: string;
}

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

function statusBadge(status: string) {
  const tones: Record<string, "green" | "amber" | "neutral" | "brick"> = {
    active: "green",
    on_hold: "amber",
    completed: "neutral",
    archived: "neutral",
  };
  return <Badge tone={tones[status] ?? "neutral"}>{status.replace(/_/g, " ")}</Badge>;
}

function Overlay({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(33, 26, 20, 0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ width: 440 }}>
        <Card>{children}</Card>
      </div>
    </div>
  );
}

/** Real project creation -- POST /v1/projects. Client/PM dropdowns are
 * genuinely optional: a project can exist before either is assigned
 * (matches real construction practice), and each dropdown degrades to
 * a clear "couldn't load" state independently if the caller lacks
 * that specific module's read permission (bdc:read for clients,
 * org:read for PMs, fin:read for companies) -- one missing permission
 * shouldn't break the whole form. */
function CreateProjectModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [companies, setCompanies] = useState<Company[] | "error" | null>(null);
  const [clients, setClients] = useState<Client[] | "error">([]);
  const [members, setMembers] = useState<OrgUser[] | "error">([]);

  const [name, setName] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [clientId, setClientId] = useState("");
  const [pmId, setPmId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiClient
      .get("/fin/companies")
      .then((res) => {
        setCompanies(res.data.data);
        if (res.data.data.length === 1) setCompanyId(res.data.data[0].id);
      })
      .catch(() => setCompanies("error"));
    apiClient
      .get("/bdc/clients")
      .then((res) => setClients(res.data.data))
      .catch(() => setClients("error"));
    apiClient
      .get("/org/members")
      .then((res) => setMembers(res.data.users))
      .catch(() => setMembers("error"));
  }, []);

  async function submit() {
    if (!name.trim() || !companyId) {
      setError("Project name and company are required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiClient.post("/projects", {
        company_id: companyId,
        name: name.trim(),
        client_id: clientId || undefined,
        project_manager_id: pmId || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      onDone();
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Overlay onClose={onClose}>
      <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 16 }}>Create Project</div>

      <Field label="Project name">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Lekki Tower Phase 1" />
      </Field>

      <Field label="Company">
        {companies === null ? (
          <Select disabled>
            <option>Loading…</option>
          </Select>
        ) : companies === "error" ? (
          <Select disabled>
            <option>Could not load companies</option>
          </Select>
        ) : (
          <Select value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
            <option value="">Select a company</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        )}
      </Field>

      <Field label="Client (optional)">
        {clients === "error" ? (
          <Select disabled>
            <option>Could not load clients</option>
          </Select>
        ) : (
          <Select value={clientId} onChange={(e) => setClientId(e.target.value)}>
            <option value="">No client yet</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        )}
      </Field>

      <Field label="Project manager (optional)">
        {members === "error" ? (
          <Select disabled>
            <option>Could not load users</option>
          </Select>
        ) : (
          <Select value={pmId} onChange={(e) => setPmId(e.target.value)}>
            <option value="">Not assigned yet</option>
            {members.map((u) => (
              <option key={u.id} value={u.id}>
                {u.email}
              </option>
            ))}
          </Select>
        )}
      </Field>

      <div style={{ display: "flex", gap: 8 }}>
        <Field label="Start date (optional)">
          <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </Field>
        <Field label="End date (optional)">
          <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </Field>
      </div>

      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginTop: 4 }}>{error}</div>}

      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <Button variant="secondary" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={submitting}>
          {submitting ? "Creating…" : "Create Project"}
        </Button>
      </div>
    </Overlay>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  async function load() {
    setError(null);
    try {
      const res = await apiClient.get("/projects", { params: { search: search || undefined, status: statusFilter || undefined } });
      setProjects(res.data.data);
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  useEffect(() => {
    const timeout = setTimeout(load, 250); // debounce search typing
    return () => clearTimeout(timeout);
  }, [search, statusFilter]);

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader
        eyebrow="Projects"
        title="All Projects"
        action={<Button onClick={() => setShowCreate(true)}>+ New Project</Button>}
      />

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <div style={{ flex: 1, maxWidth: 320 }}>
          <Input placeholder="Search projects…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div style={{ width: 180 }}>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="on_hold">On hold</option>
            <option value="completed">Completed</option>
            <option value="archived">Archived</option>
          </Select>
        </div>
      </div>

      {error && <ErrorBanner title="Something went wrong" detail={error} onDismiss={() => setError(null)} />}

      <Card style={{ padding: 0 }}>
        {projects === null ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : projects.length === 0 ? (
          <EmptyState title="No projects yet" hint="Create your first project to get started." />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Start date</Th>
                <Th>End date</Th>
                <Th>Status</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id}>
                  <Td>{p.name}</Td>
                  <Td mono>{p.start_date || "—"}</Td>
                  <Td mono>{p.end_date || "—"}</Td>
                  <Td>{statusBadge(p.status)}</Td>
                  <Td style={{ textAlign: "right" }}>
                    <Link to={`/projects/${p.id}`}>
                      <Button variant="ghost">View</Button>
                    </Link>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {showCreate && (
        <CreateProjectModal
          onClose={() => setShowCreate(false)}
          onDone={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </div>
  );
}
