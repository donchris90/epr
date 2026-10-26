import { useState } from "react";
import { PageHeader, Card, Button, Input, Field } from "../../components/ui";
import { VendorSelect } from "../../components/VendorSelect";
import { useCreateVendorUser } from "./hooks";
import BankingChangeReview from "./BankingChangeReview";

export default function VendorPortalAdminPage() {
  const createVendorUser = useCreateVendorUser();
  const [userForm, setUserForm] = useState({ vendor_id: "", email: "", password: "" });

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

      <BankingChangeReview />
    </div>
  );
}
