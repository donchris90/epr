import { useMemo, useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import {
  useJournalEntries,
  useCompanies,
  useChartOfAccounts,
  useAPInvoices,
  usePostAPInvoice,
  useARInvoices,
  usePostARInvoice,
  usePostManualException,
} from "./hooks";

type Line = { account_id: string; debit_amount: string; credit_amount: string };

export default function LedgerPage() {
  const { data: entries, isLoading } = useJournalEntries();
  const { data: companies } = useCompanies();
  const { data: accounts } = useChartOfAccounts();
  const { data: apInvoices } = useAPInvoices();
  const { data: arInvoices } = useARInvoices();

  const postAP = usePostAPInvoice();
  const postAR = usePostARInvoice();
  const postException = usePostManualException();

  const [tab, setTab] = useState<"ledger" | "ap" | "ar" | "exception">("ledger");

  return (
    <div>
      <PageHeader eyebrow="Financial Management" title="Ledger" />

      <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
        {(["ledger", "ap", "ar", "exception"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "6px 12px",
              fontSize: 12,
              fontWeight: 600,
              border: "none",
              background: "none",
              cursor: "pointer",
              color: tab === t ? "var(--sf-navy-900)" : "var(--sf-navy-400)",
              borderBottom: tab === t ? "2px solid var(--sf-amber)" : "2px solid transparent",
            }}
          >
            {t === "ledger" ? "Journal Entries" : t === "ap" ? "Post AP Invoice" : t === "ar" ? "Post AR Invoice" : "Manual Exception"}
          </button>
        ))}
      </div>

      {tab === "ledger" && (
        <>
          {isLoading ? (
            <p>Loading…</p>
          ) : !entries?.length ? (
            <EmptyState title="No journal entries yet" hint="Every entry here is traceable to the module that posted it." />
          ) : (
            <Card style={{ padding: 0 }}>
              <Table>
                <thead>
                  <tr>
                    <Th>Date</Th>
                    <Th>Source module</Th>
                    <Th>Description</Th>
                    <Th>Status</Th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e: any) => (
                    <tr key={e.id}>
                      <Td mono>{e.entry_date}</Td>
                      <Td>
                        <Badge tone={e.source_module === "manual_exception" ? "amber" : "steel"}>{e.source_module}</Badge>
                      </Td>
                      <Td>{e.description || "—"}</Td>
                      <Td>
                        <Badge tone="green">{e.status}</Badge>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          )}
        </>
      )}

      {tab === "ap" && (
        <APInvoiceForm companies={companies ?? []} accounts={accounts ?? []} postAP={postAP} invoices={apInvoices ?? []} />
      )}

      {tab === "ar" && (
        <ARInvoiceForm companies={companies ?? []} accounts={accounts ?? []} postAR={postAR} invoices={arInvoices ?? []} />
      )}

      {tab === "exception" && (
        <ManualExceptionForm companies={companies ?? []} accounts={accounts ?? []} postException={postException} />
      )}
    </div>
  );
}

function APInvoiceForm({ companies, accounts, postAP, invoices }: any) {
  const [form, setForm] = useState({
    company_id: "",
    invoice_number: "",
    amount: "",
    expense_account_id: "",
    payable_account_id: "",
  });
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await postAP.mutateAsync({ ...form, source_module: "manual_entry" });
      setForm({ company_id: form.company_id, invoice_number: "", amount: "", expense_account_id: "", payable_account_id: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 4 }}>Post an Accounts Payable invoice</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        Debits the expense account, credits the payable account — a balanced entry every time.
      </p>
      {error && <ErrorBanner title="Could not post invoice" detail={error} onDismiss={() => setError(null)} />}
      <form onSubmit={handleSubmit}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <Field label="Company">
            <AccountSelect value={form.company_id} onChange={(v) => setForm({ ...form, company_id: v })} options={companies} />
          </Field>
          <Field label="Invoice number">
            <Input required value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} />
          </Field>
          <Field label="Amount">
            <Input required value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </Field>
          <Field label="Expense account (Dr)">
            <AccountSelect value={form.expense_account_id} onChange={(v) => setForm({ ...form, expense_account_id: v })} options={accounts} labelKey="code" />
          </Field>
          <Field label="Payable account (Cr)">
            <AccountSelect value={form.payable_account_id} onChange={(v) => setForm({ ...form, payable_account_id: v })} options={accounts} labelKey="code" />
          </Field>
        </div>
        <Button type="submit" disabled={postAP.isPending}>
          {postAP.isPending ? "Posting…" : "Post invoice"}
        </Button>
      </form>

      {invoices.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <Table>
            <thead>
              <tr>
                <Th>Invoice</Th>
                <Th>Amount</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv: any) => (
                <tr key={inv.id}>
                  <Td mono>{inv.invoice_number}</Td>
                  <Td mono>{inv.amount}</Td>
                  <Td>
                    <Badge tone={inv.status === "paid" ? "green" : "neutral"}>{inv.status}</Badge>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </Card>
  );
}

function ARInvoiceForm({ companies, accounts, postAR, invoices }: any) {
  const [form, setForm] = useState({
    company_id: "",
    invoice_number: "",
    amount: "",
    receivable_account_id: "",
    revenue_account_id: "",
  });
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await postAR.mutateAsync({ ...form, source_module: "manual_entry" });
      setForm({ company_id: form.company_id, invoice_number: "", amount: "", receivable_account_id: "", revenue_account_id: "" });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 4 }}>Post an Accounts Receivable invoice</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        Debits the receivable account, credits revenue — the actual figure Module 21's dashboard reads.
      </p>
      {error && <ErrorBanner title="Could not post invoice" detail={error} onDismiss={() => setError(null)} />}
      <form onSubmit={handleSubmit}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <Field label="Company">
            <AccountSelect value={form.company_id} onChange={(v) => setForm({ ...form, company_id: v })} options={companies} />
          </Field>
          <Field label="Invoice number">
            <Input required value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} />
          </Field>
          <Field label="Amount">
            <Input required value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </Field>
          <Field label="Receivable account (Dr)">
            <AccountSelect value={form.receivable_account_id} onChange={(v) => setForm({ ...form, receivable_account_id: v })} options={accounts} labelKey="code" />
          </Field>
          <Field label="Revenue account (Cr)">
            <AccountSelect value={form.revenue_account_id} onChange={(v) => setForm({ ...form, revenue_account_id: v })} options={accounts} labelKey="code" />
          </Field>
        </div>
        <Button type="submit" disabled={postAR.isPending}>
          {postAR.isPending ? "Posting…" : "Post invoice"}
        </Button>
      </form>

      {invoices.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <Table>
            <thead>
              <tr>
                <Th>Invoice</Th>
                <Th>Amount</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv: any) => (
                <tr key={inv.id}>
                  <Td mono>{inv.invoice_number}</Td>
                  <Td mono>{inv.amount}</Td>
                  <Td>
                    <Badge tone={inv.status === "paid" ? "green" : "neutral"}>{inv.status}</Badge>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </Card>
  );
}

function ManualExceptionForm({ companies, accounts, postException }: any) {
  const [companyId, setCompanyId] = useState("");
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState<Line[]>([
    { account_id: "", debit_amount: "", credit_amount: "" },
    { account_id: "", debit_amount: "", credit_amount: "" },
  ]);
  const [error, setError] = useState<string | null>(null);

  const totals = useMemo(() => {
    const debit = lines.reduce((sum, l) => sum + (parseFloat(l.debit_amount) || 0), 0);
    const credit = lines.reduce((sum, l) => sum + (parseFloat(l.credit_amount) || 0), 0);
    return { debit, credit, balanced: debit === credit && debit > 0 };
  }, [lines]);

  function updateLine(index: number, patch: Partial<Line>) {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, { account_id: "", debit_amount: "", credit_amount: "" }]);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await postException.mutateAsync({
        company_id: companyId,
        description,
        lines: lines
          .filter((l) => l.account_id)
          .map((l) => ({ account_id: l.account_id, debit_amount: l.debit_amount || "0", credit_amount: l.credit_amount || "0" })),
      });
      setDescription("");
      setLines([
        { account_id: "", debit_amount: "", credit_amount: "" },
        { account_id: "", debit_amount: "", credit_amount: "" },
      ]);
    } catch (err) {
      // Requires the fin:manual_exception permission specifically —
      // an ordinary fin:write session will get a 403 here, which is
      // the business rule working as intended, not a bug.
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 4 }}>Manual exception posting</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        The only journal posting not tied to a real originating module — requires the distinct{" "}
        <code className="sf-mono">fin:manual_exception</code> permission, and every entry must balance before it can
        be submitted at all.
      </p>

      {error && <ErrorBanner title="Could not post entry" detail={error} onDismiss={() => setError(null)} />}

      <form onSubmit={handleSubmit}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 16, marginBottom: 16 }}>
          <Field label="Company">
            <AccountSelect value={companyId} onChange={setCompanyId} options={companies} />
          </Field>
          <Field label="Description">
            <Input required value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
        </div>

        <div style={{ marginBottom: 8, fontSize: 12, fontWeight: 600, color: "var(--sf-navy-400)" }}>Lines</div>
        {lines.map((line, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
            <AccountSelect
              value={line.account_id}
              onChange={(v) => updateLine(i, { account_id: v })}
              options={accounts}
              labelKey="code"
              placeholder="Account"
            />
            <Input
              placeholder="Debit"
              value={line.debit_amount}
              onChange={(e) => updateLine(i, { debit_amount: e.target.value, credit_amount: e.target.value ? "" : line.credit_amount })}
            />
            <Input
              placeholder="Credit"
              value={line.credit_amount}
              onChange={(e) => updateLine(i, { credit_amount: e.target.value, debit_amount: e.target.value ? "" : line.debit_amount })}
            />
          </div>
        ))}
        <button
          type="button"
          onClick={addLine}
          style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer", marginBottom: 16 }}
        >
          + Add line
        </button>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            padding: "10px 14px",
            marginBottom: 16,
            borderRadius: "var(--sf-radius)",
            fontSize: 13,
            background: totals.balanced ? "var(--sf-green-dim)" : "var(--sf-brick-dim)",
            border: `1px solid ${totals.balanced ? "var(--sf-green)" : "var(--sf-brick)"}`,
          }}
        >
          <span className="sf-mono">Debits: {totals.debit.toLocaleString()}</span>
          <span className="sf-mono">Credits: {totals.credit.toLocaleString()}</span>
          <strong style={{ color: totals.balanced ? "var(--sf-green)" : "var(--sf-brick)" }}>
            {totals.balanced ? "Balanced" : "Not balanced"}
          </strong>
        </div>

        <Button type="submit" disabled={!totals.balanced || postException.isPending}>
          {postException.isPending ? "Posting…" : "Post entry"}
        </Button>
      </form>
    </Card>
  );
}

function AccountSelect({
  value,
  onChange,
  options,
  labelKey = "name",
  placeholder = "Select…",
}: {
  value: string;
  onChange: (v: string) => void;
  options: any[];
  labelKey?: string;
  placeholder?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{ padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, width: "100%", background: "#fff" }}
    >
      <option value="">{placeholder}</option>
      {options.map((o: any) => (
        <option key={o.id} value={o.id}>
          {labelKey === "code" ? `${o.code} — ${o.name}` : o.name}
        </option>
      ))}
    </select>
  );
}
