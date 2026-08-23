import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../../api/client";
import { useWorkflowDefinitions } from "./hooks";
import { hasPermission } from "../../lib/permissions";
import { PageHeader, Card, Table, Th, Td, Badge, Button, Input, Select, Field, ErrorBanner, EmptyState } from "../../components/ui";

const PAGE_SIZE = 20;

/** Real Workflow List, backed by GET /v1/workflow/definitions
 * (app/workflow/routes.py). Search and status (active/inactive)
 * filtering happen client-side over the fetched set -- the backend
 * doesn't offer a text-search or an active-only query param (only
 * module_name/entity_type, both applied as real, server-side
 * filters). Pagination is also client-side for the same reason: the
 * backend returns every matching row with no limit/offset support.
 *
 * BACKEND GAP: no text search, active-only filter, or pagination
 * exists on GET /v1/workflow/definitions. For the realistic number of
 * workflow definitions a tenant would actually configure (a handful
 * per module, not thousands), this is a reasonable frontend-side
 * approximation rather than a real limitation in practice -- but it's
 * a real, worth-noting gap if that assumption ever stops holding. */
export default function WorkflowListPage() {
  const [moduleFilter, setModuleFilter] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | "active" | "inactive">("");
  const [page, setPage] = useState(1);
  const [members, setMembers] = useState<Map<string, string>>(new Map());

  const { definitions, loading, error } = useWorkflowDefinitions(moduleFilter ? { module_name: moduleFilter } : undefined);

  useEffect(() => {
    apiClient
      .get("/org/members")
      .then((res) => {
        const map = new Map<string, string>();
        for (const u of res.data.users) map.set(u.id, u.email);
        setMembers(map);
      })
      .catch(() => {});
  }, []);

  const canManage = hasPermission("workflow:admin");

  const filtered = useMemo(() => {
    if (!definitions) return [];
    let result = definitions;
    if (statusFilter) {
      result = result.filter((d) => (statusFilter === "active" ? d.active : !d.active));
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (d) => d.workflow_name.toLowerCase().includes(q) || (d.description ?? "").toLowerCase().includes(q)
      );
    }
    return result;
  }, [definitions, statusFilter, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function resolveName(id: string | null) {
    if (!id) return "—";
    return members.get(id) ?? id;
  }

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader
        eyebrow="Workflow Engine"
        title="Workflows"
        action={
          canManage ? (
            <Link to="/workflows/new">
              <Button>+ New Workflow</Button>
            </Link>
          ) : undefined
        }
      />

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
        <Field label="Search">
          <Input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search by name or description…"
          />
        </Field>
        <Field label="Module">
          <Select
            value={moduleFilter}
            onChange={(e) => {
              setModuleFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All modules</option>
            <option value="prc">Procurement (prc)</option>
            <option value="ctm">Contracts (ctm)</option>
            <option value="est">Estimating (est)</option>
            <option value="hse">HSE (hse)</option>
          </Select>
        </Field>
        <Field label="Status">
          <Select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as "" | "active" | "inactive");
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive / Draft</option>
          </Select>
        </Field>
      </div>

      {error && <ErrorBanner title="Something went wrong" detail={error} />}

      <Card style={{ padding: 0 }}>
        {loading ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No workflows found"
            hint={definitions?.length ? "Try a different search or filter." : "Create your first workflow to get started."}
          />
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Workflow name</Th>
                  <Th>Module / Entity</Th>
                  <Th>Version</Th>
                  <Th>Status</Th>
                  <Th>Created by</Th>
                  <Th>Updated</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {pageItems.map((d) => (
                  <tr key={d.id}>
                    <Td>
                      <div style={{ fontWeight: 600 }}>{d.workflow_name}</div>
                      {d.description && <div style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>{d.description}</div>}
                    </Td>
                    <Td mono>
                      {d.module_name} / {d.entity_type}
                    </Td>
                    <Td mono>v{d.version}</Td>
                    <Td>
                      <Badge tone={d.active ? "green" : "neutral"}>{d.active ? "Active" : "Draft"}</Badge>
                    </Td>
                    <Td>{resolveName(d.created_by)}</Td>
                    <Td mono>{new Date(d.updated_at).toLocaleDateString()}</Td>
                    <Td style={{ textAlign: "right" }}>
                      <Link to={`/workflows/${d.id}`}>
                        <Button variant="ghost">View</Button>
                      </Link>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            {totalPages > 1 && (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: 16, borderTop: "1px solid var(--sf-line)" }}>
                <span style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>
                  Page {page} of {totalPages} ({filtered.length} workflows)
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  <Button variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button variant="ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
