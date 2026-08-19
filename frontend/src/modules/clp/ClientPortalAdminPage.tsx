import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field } from "../../components/ui";
import { useCreateClientUser, useAssignClientToProject, useClientRequests, useResolveClientRequest } from "./hooks";

export default function ClientPortalAdminPage() {
  const createClientUser = useCreateClientUser();
  const [userForm, setUserForm] = useState({ client_organization_name: "", email: "" });
  const [createdUser, setCreatedUser] = useState<any>(null);

  const assignToProject = useAssignClientToProject();
  const [projectId, setProjectId] = useState("");

  const { data: requests, isLoading } = useClientRequests(createdUser?.id);
  const resolveRequest = useResolveClientRequest();
  const [responses, setResponses] = useState<Record<string, string>>({});

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    const res = await createClientUser.mutateAsync(userForm);
    setCreatedUser(res.data);
    setUserForm({ client_organization_name: "", email: "" });
  }

  async function handleAssign(e: React.FormEvent) {
    e.preventDefault();
    if (!createdUser) return;
    await assignToProject.mutateAsync({ clientUserId: createdUser.id, project_id: projectId });
    setProjectId("");
  }

  async function handleResolve(requestId: string) {
    await resolveRequest.mutateAsync({ requestId, response: responses[requestId] || "" });
  }

  return (
    <div>
      <PageHeader eyebrow="Client Portal" title="Client Users & Project Assignments" />

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Register a client user</h3>
          <form onSubmit={handleCreateUser}>
            <Field label="Client organization">
              <Input required value={userForm.client_organization_name} onChange={(e) => setUserForm({ ...userForm, client_organization_name: e.target.value })} />
            </Field>
            <Field label="Email">
              <Input required type="email" value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} />
            </Field>
            <Button type="submit" disabled={createClientUser.isPending}>{createClientUser.isPending ? "Creating…" : "Create"}</Button>
          </form>
          {createdUser && (
            <div style={{ marginTop: 12, fontSize: 12, color: "var(--sf-navy-400)" }}>
              Created: <span className="sf-mono">{createdUser.client_organization_name}</span>
            </div>
          )}
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>Assign to a project</h3>
          <p style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 12 }}>
            This assignment is the only thing that grants portal access to a project — a client can never see
            another project's data, regardless of any other permission.
          </p>
          <form onSubmit={handleAssign} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
            <Input required placeholder="Project ID" value={projectId} onChange={(e) => setProjectId(e.target.value)} disabled={!createdUser} />
            <Button type="submit" disabled={assignToProject.isPending || !createdUser}>Assign</Button>
          </form>
        </Card>
      </div>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Client requests</h3>
        {!createdUser ? (
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>Create/select a client user above to view their requests.</p>
        ) : isLoading ? (
          <p>Loading…</p>
        ) : !requests?.length ? (
          <EmptyState title="No requests yet" hint="RFIs and other requests raised through the client portal appear here." />
        ) : (
          <Table>
            <thead><tr><Th>Type</Th><Th>Description</Th><Th>Status</Th><Th></Th></tr></thead>
            <tbody>
              {requests.map((r: any) => (
                <tr key={r.id}>
                  <Td><Badge tone="neutral">{r.request_type}</Badge></Td>
                  <Td>{r.description}</Td>
                  <Td><Badge tone={r.status === "resolved" ? "green" : "amber"}>{r.status}</Badge></Td>
                  <Td>
                    {r.status !== "resolved" && (
                      <div style={{ display: "flex", gap: 6 }}>
                        <Input
                          placeholder="Response"
                          value={responses[r.id] || ""}
                          onChange={(e) => setResponses({ ...responses, [r.id]: e.target.value })}
                          style={{ width: 140, fontSize: 11 }}
                        />
                        <button
                          disabled={!responses[r.id]}
                          onClick={() => handleResolve(r.id)}
                          style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                        >
                          Resolve
                        </button>
                      </div>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
