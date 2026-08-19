import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Input } from "../../components/ui";
import { useCompanies, useCreateCompany, useChartOfAccounts, useCreateAccount } from "./hooks";

const ACCOUNT_TYPES = ["asset", "liability", "equity", "revenue", "expense"];

export default function SetupPage() {
  const { data: companies } = useCompanies();
  const createCompany = useCreateCompany();
  const [companyForm, setCompanyForm] = useState({ name: "", functional_currency: "NGN" });

  const { data: accounts } = useChartOfAccounts();
  const createAccount = useCreateAccount();
  const [accountForm, setAccountForm] = useState({ code: "", name: "", account_type: "expense" });

  async function handleCreateCompany(e: React.FormEvent) {
    e.preventDefault();
    await createCompany.mutateAsync(companyForm);
    setCompanyForm({ name: "", functional_currency: "NGN" });
  }

  async function handleCreateAccount(e: React.FormEvent) {
    e.preventDefault();
    await createAccount.mutateAsync(accountForm);
    setAccountForm({ code: "", name: "", account_type: "expense" });
  }

  return (
    <div>
      <PageHeader eyebrow="Financial Management" title="Setup" />

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Companies</h3>
          <form onSubmit={handleCreateCompany} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: 8, marginBottom: 16 }}>
            <Input
              required
              placeholder="Company name"
              value={companyForm.name}
              onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })}
            />
            <Input
              placeholder="NGN"
              value={companyForm.functional_currency}
              onChange={(e) => setCompanyForm({ ...companyForm, functional_currency: e.target.value })}
            />
            <Button type="submit" disabled={createCompany.isPending}>
              Add
            </Button>
          </form>
          {companies?.length ? (
            <ul style={{ margin: 0, padding: 0, listStyle: "none", fontSize: 13 }}>
              {companies.map((c: any) => (
                <li key={c.id} style={{ padding: "8px 0", borderBottom: "1px solid var(--sf-line)", display: "flex", justifyContent: "space-between" }}>
                  <span>{c.name}</span>
                  <span className="sf-mono" style={{ color: "var(--sf-navy-400)" }}>
                    {c.functional_currency}
                    {c.is_default && (
                      <>
                        {" "}
                        <Badge tone="steel">Default</Badge>
                      </>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No companies yet.</p>
          )}
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Chart of accounts</h3>
          <form onSubmit={handleCreateAccount} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr 1fr auto", gap: 8, marginBottom: 16 }}>
            <Input
              required
              placeholder="Code"
              value={accountForm.code}
              onChange={(e) => setAccountForm({ ...accountForm, code: e.target.value })}
            />
            <Input
              required
              placeholder="Account name"
              value={accountForm.name}
              onChange={(e) => setAccountForm({ ...accountForm, name: e.target.value })}
            />
            <select
              value={accountForm.account_type}
              onChange={(e) => setAccountForm({ ...accountForm, account_type: e.target.value })}
              style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" }}
            >
              {ACCOUNT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <Button type="submit" disabled={createAccount.isPending}>
              Add
            </Button>
          </form>
          {accounts?.length ? (
            <Table>
              <thead>
                <tr>
                  <Th>Code</Th>
                  <Th>Name</Th>
                  <Th>Type</Th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a: any) => (
                  <tr key={a.id}>
                    <Td mono>{a.code}</Td>
                    <Td>{a.name}</Td>
                    <Td>
                      <Badge tone="neutral">{a.account_type}</Badge>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <p style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>No accounts yet.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
