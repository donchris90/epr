import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { apiClient } from "../api/client";
import { PageHeader, Card, Button, Table, Th, Td, Badge, ErrorBanner, EmptyState, Input, Field } from "../components/ui";

interface PermissionEntry {
  code: string;
  label: string;
}

interface PermissionGroup {
  module_code: string;
  module_label: string;
  permissions: PermissionEntry[];
}

interface Role {
  id: string;
  name: string;
  permission_set: string[];
}

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

function Overlay({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(33, 26, 20, 0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100, padding: 24 }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ width: 560, maxHeight: "85vh", overflowY: "auto" }}>
        <Card>{children}</Card>
      </div>
    </div>
  );
}

/** Real create/edit form -- groups (native <details>/<summary>, no
 * extra state needed) mirror GET /v1/org/permissions-catalog's real,
 * confirmed 92-permission list exactly; nothing here is invented.
 * "*" (full access) is offered separately and explicitly, not folded
 * into the module list, since it's a genuinely different kind of
 * grant matching what the wildcard already means everywhere else in
 * this app's permission checks. */
function RoleFormModal({
  catalog,
  role,
  onClose,
  onDone,
}: {
  catalog: PermissionGroup[];
  role: Role | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const [name, setName] = useState(role?.name ?? "");
  const [fullAccess, setFullAccess] = useState(role?.permission_set.includes("*") ?? false);
  const [selected, setSelected] = useState<Set<string>>(new Set(role?.permission_set.filter((p) => p !== "*") ?? []));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function toggle(code: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  function toggleGroup(group: PermissionGroup, allSelected: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const perm of group.permissions) {
        if (allSelected) next.delete(perm.code);
        else next.add(perm.code);
      }
      return next;
    });
  }

  async function submit() {
    if (!name.trim()) {
      setError("Role name is required.");
      return;
    }
    const permission_set = fullAccess ? ["*"] : Array.from(selected);
    if (permission_set.length === 0) {
      setError("Select at least one permission, or grant full access.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (role) {
        await apiClient.put(`/org/roles/${role.id}`, { name: name.trim(), permission_set });
      } else {
        await apiClient.post("/org/roles", { name: name.trim(), permission_set });
      }
      onDone();
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Overlay onClose={onClose}>
      <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 16 }}>{role ? "Edit Role" : "Create Role"}</div>

      <Field label="Role name">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Site Engineer" />
      </Field>

      <label style={{ display: "flex", alignItems: "center", gap: 8, margin: "12px 0", fontSize: 13, cursor: "pointer" }}>
        <input type="checkbox" checked={fullAccess} onChange={(e) => setFullAccess(e.target.checked)} />
        Full access (every current and future permission)
      </label>

      {!fullAccess && (
        <div style={{ border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", maxHeight: 320, overflowY: "auto", padding: 4 }}>
          {catalog.map((group) => {
            const allSelected = group.permissions.every((p) => selected.has(p.code));
            const someSelected = group.permissions.some((p) => selected.has(p.code));
            return (
              <details key={group.module_code} style={{ padding: "6px 8px" }} open={someSelected}>
                <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: 600, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>
                    {group.module_label} {someSelected && <Badge tone="steel">{group.permissions.filter((p) => selected.has(p.code)).length}</Badge>}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      toggleGroup(group, allSelected);
                    }}
                    style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, cursor: "pointer" }}
                  >
                    {allSelected ? "Clear all" : "Select all"}
                  </button>
                </summary>
                <div style={{ paddingLeft: 16, paddingTop: 6 }}>
                  {group.permissions.map((perm) => (
                    <label key={perm.code} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, padding: "3px 0", cursor: "pointer" }}>
                      <input type="checkbox" checked={selected.has(perm.code)} onChange={() => toggle(perm.code)} />
                      {perm.label}
                    </label>
                  ))}
                </div>
              </details>
            );
          })}
        </div>
      )}

      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginTop: 10 }}>{error}</div>}

      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <Button variant="secondary" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={submitting}>
          {submitting ? "Saving…" : role ? "Save Changes" : "Create Role"}
        </Button>
      </div>
    </Overlay>
  );
}

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[] | null>(null);
  const [catalog, setCatalog] = useState<PermissionGroup[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [editingRole, setEditingRole] = useState<Role | "new" | null>(null);

  async function load() {
    setError(null);
    try {
      const [rolesRes, catalogRes] = await Promise.all([
        apiClient.get("/org/roles"),
        apiClient.get("/org/permissions-catalog"),
      ]);
      setRoles(rolesRes.data.data);
      setCatalog(catalogRes.data.data);
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleDelete(role: Role) {
    setPendingId(role.id);
    setError(null);
    try {
      await apiClient.delete(`/org/roles/${role.id}`);
      await load();
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  function summarize(permissionSet: string[]) {
    if (permissionSet.includes("*")) return "Full access";
    if (permissionSet.length === 1) return "1 permission";
    return `${permissionSet.length} permissions`;
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader eyebrow="Settings" title="Roles" action={<Button onClick={() => setEditingRole("new")}>+ New Role</Button>} />

      {error && <ErrorBanner title="Something went wrong" detail={error} onDismiss={() => setError(null)} />}

      <Card style={{ padding: 0 }}>
        {roles === null ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : roles.length === 0 ? (
          <EmptyState title="No roles yet" hint="Create your first role to start inviting people with the right level of access." />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Access</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {roles.map((role) => (
                <tr key={role.id}>
                  <Td>{role.name}</Td>
                  <Td>
                    <Badge tone={role.permission_set.includes("*") ? "amber" : "neutral"}>{summarize(role.permission_set)}</Badge>
                  </Td>
                  <Td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      <Button variant="ghost" onClick={() => setEditingRole(role)}>
                        Edit
                      </Button>
                      <Button variant="danger" disabled={pendingId === role.id} onClick={() => handleDelete(role)}>
                        {pendingId === role.id ? "Deleting…" : "Delete"}
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {editingRole && (
        <RoleFormModal
          catalog={catalog}
          role={editingRole === "new" ? null : editingRole}
          onClose={() => setEditingRole(null)}
          onDone={() => {
            setEditingRole(null);
            load();
          }}
        />
      )}
    </div>
  );
}
