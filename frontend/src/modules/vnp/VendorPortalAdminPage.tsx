import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, EmptyState, Input, Field } from "../../components/ui";
import { VendorSelect } from "../../components/VendorSelect";
import { useCreateVendorUser, useBankingChangeRequests, useApproveBankingChange, useRejectBankingChange } from "./hooks";

export default function VendorPortalAdminPage() {
  const createVendorUser = useCreateVendorUser();
  const [userForm, setUserForm] = useState({ vendor_id: "", email: "", password: "" });

  const { data: requests, isLoading } = useBankingChangeRequests("pending");
  const approve = useApproveBankingChange();
  const reject = useRejectBankingChange();
  const [rejectReason, setRejectReason] = useState<Record<string, string>>({});

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    await createVendorUser.mutateAsync(userForm);
    setUserForm({ vendor_id: "", email: "", password: "" });
  }

  return (
    <div>
      <PageHeader eyebrow="Vendor Portal" title="Vendor Users & Banking Changes" />

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Register a vendor portal user</h3>
        <form onSubmit={handleCreateUser} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 12 }}>
          <Field label="Vendor">
            <VendorSelect required value={userForm.vendor_id} onChange={(vendor_id) => setUserForm({ ...userForm, vendor_id })} />
          </Field>
          <Field label="Email">
            <Input required type="email" value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} />
          </Field>
          <Field label="Temporary password" hint="At least 8 characters — the vendor should change this after first sign-in.">
            <Input required type="password" minLength={8} value={userForm.password} onChange={(e) => setUserForm({ ...userForm, password: e.target.value })} />
          </Field>
          <Button type="submit" disabled={createVendorUser.isPending} style={{ height: 38, alignSelf: "end" }}>
            {createVendorUser.isPending ? "Creating…" : "Create"}
          </Button>
        </form>
      </Card>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Pending banking change requests</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
          A vendor-submitted change never touches the live vendor record — it takes explicit approval here,
          held behind a permission a vendor-portal session can never have.
        </p>
        {isLoading ? (
          <p>Loading…</p>
        ) : !requests?.length ? (
          <EmptyState title="Nothing pending" hint="Banking detail changes submitted through the vendor portal appear here for review." />
        ) : (
          <Table>
            <thead><tr><Th>Vendor</Th><Th>Proposed details</Th><Th></Th></tr></thead>
            <tbody>
              {requests.map((r: any) => (
                <tr key={r.id}>
                  <Td mono style={{ fontSize: 11 }}>{r.vendor_id.slice(0, 8)}…</Td>
                  <Td mono style={{ fontSize: 11 }}>{JSON.stringify(r.proposed_banking_details)}</Td>
                  <Td>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <button onClick={() => approve.mutate(r.id)} style={{ background: "none", border: "none", color: "var(--sf-green)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                        Approve
                      </button>
                      <Input
                        placeholder="Rejection reason"
                        value={rejectReason[r.id] || ""}
                        onChange={(e) => setRejectReason({ ...rejectReason, [r.id]: e.target.value })}
                        style={{ width: 130, fontSize: 11 }}
                      />
                      <button
                        disabled={!rejectReason[r.id]}
                        onClick={() => reject.mutate({ requestId: r.id, reason: rejectReason[r.id] })}
                        style={{ background: "none", border: "none", color: "var(--sf-brick)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                      >
                        Reject
                      </button>
                    </div>
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
