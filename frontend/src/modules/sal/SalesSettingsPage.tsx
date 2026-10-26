import { useEffect, useState } from "react";
import { PageHeader, Card, Button, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useChartOfAccounts, useCompanies } from "../fin/hooks";
import { useSalesSettings, useSaveSalesSettings } from "./hooks";

const selectStyle = { padding: "8px 10px", border: "1px solid var(--sf-line)", borderRadius: "var(--sf-radius)", fontSize: 13, background: "#fff" };

export default function SalesSettingsPage() {
  const { data: settings } = useSalesSettings();
  const { data: companies } = useCompanies();
  const { data: accounts } = useChartOfAccounts();
  const save = useSaveSalesSettings();
  const [form, setForm] = useState({
    company_id: "",
    receivable_account_id: "",
    revenue_account_id: "",
    vat_account_id: "",
    vat_percent: "7.5",
    payment_terms_days: "30",
  });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (settings)
      setForm({
        company_id: settings.company_id,
        receivable_account_id: settings.receivable_account_id,
        revenue_account_id: settings.revenue_account_id,
        vat_account_id: settings.vat_account_id ?? "",
        vat_percent: String(Number(settings.vat_percent)),
        payment_terms_days: String(settings.payment_terms_days),
      });
  }, [settings]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    try {
      await save.mutateAsync({
        ...form,
        vat_account_id: form.vat_account_id || null,
        payment_terms_days: Number(form.payment_terms_days),
      });
      setSaved(true);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  const accountSelect = (key: "receivable_account_id" | "revenue_account_id" | "vat_account_id", label: string, required: boolean) => (
    <Field label={label}>
      <select aria-label={label} required={required} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} style={selectStyle}>
        <option value="">{required ? "Select account…" : "None"}</option>
        {accounts?.map((a: any) => (
          <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
        ))}
      </select>
    </Field>
  );

  return (
    <div>
      <PageHeader eyebrow="Sales" title="Accounting settings" />
      <Card>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
          Sales invoices post to the ledger: the customer owes the total, revenue is credited with the net amount, and VAT is credited to the VAT account.
        </p>
        {error && <ErrorBanner title="Couldn't save settings" detail={error} onDismiss={() => setError(null)} />}
        {saved && <p role="status" style={{ fontSize: 12, color: "var(--sf-green)", marginBottom: 8 }}>Settings saved.</p>}
        <form onSubmit={submit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          <Field label="Company">
            <select aria-label="Company" required value={form.company_id} onChange={(e) => setForm({ ...form, company_id: e.target.value })} style={selectStyle}>
              <option value="">Select company…</option>
              {companies?.map((c: any) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </Field>
          {accountSelect("receivable_account_id", "Receivable account", true)}
          {accountSelect("revenue_account_id", "Revenue account", true)}
          {accountSelect("vat_account_id", "VAT account (output VAT payable)", false)}
          <Field label="VAT rate (%)">
            <Input inputMode="decimal" required value={form.vat_percent} onChange={(e) => setForm({ ...form, vat_percent: e.target.value })} />
          </Field>
          <Field label="Payment terms (days)">
            <Input inputMode="numeric" required value={form.payment_terms_days} onChange={(e) => setForm({ ...form, payment_terms_days: e.target.value })} />
          </Field>
          <div>
            <Button type="submit" disabled={save.isPending}>Save settings</Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
