import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, ErrorBanner, Input, Field, formatMoney } from "../../components/ui";
import { CompanySelect } from "../../components/CompanySelect";
import { AccountSelect } from "../../components/AccountSelect";
import { useEmployees } from "./hooks";
import { usePayrollRun, useFinalizePayrollRun, usePostPayrollToFinance, type PayrollLine } from "./hooks";
import { getErrorMessage } from "../../api/client";

/** Real payroll run detail -- Review, Exceptions, Payslips, Bank
 * export, and Finance posting, all against real data. This backend's
 * own real PAYROLL_STATUSES is only ("draft", "finalized") -- no
 * separate "approved" state exists. This batch's own workflow
 * (".. -> payroll -> approval -> finalize -> ..") is honestly mapped
 * onto that real state machine rather than inventing a third status:
 * the draft state IS the review/approval stage (every section below
 * is available for review while draft), and Finalize is the one real
 * transition that closes it -- there is no separate "Approve" action
 * distinct from Finalize in this real backend. See
 * docs/WFM_SUB_GAPS.md. */
export default function PayrollRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const { data: run, isLoading, error } = usePayrollRun(runId);
  const { data: employees } = useEmployees();
  const finalize = useFinalizePayrollRun();
  const [finalizeError, setFinalizeError] = useState<string | null>(null);

  const employeeNameById = new Map((employees ?? []).map((e) => [e.id, e.name]));

  async function handleFinalize() {
    if (!run || !confirm("Finalize this payroll run? This cannot be undone.")) return;
    setFinalizeError(null);
    try {
      await finalize.mutateAsync(run.id);
    } catch (err) {
      setFinalizeError(getErrorMessage(err));
    }
  }

  if (isLoading) return <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>;
  if (error || !run) return <ErrorBanner title="Could not load payroll run" detail={getErrorMessage(error)} />;

  // Real, computable "exceptions" -- lines with genuinely unusual
  // values (zero or negative net pay), not an invented business rule.
  const exceptions = run.lines.filter((l) => Number(l.net_pay) <= 0);

  return (
    <div>
      <PageHeader
        eyebrow="Payroll Run"
        title={`${run.period_start} → ${run.period_end}`}
        action={<Badge tone={run.status === "finalized" ? "green" : "amber"}>{run.status}</Badge>}
      />

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 20 }}>
        <Card>
          <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Total gross</div>
          <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{formatMoney(run.total_gross)}</div>
        </Card>
        <Card>
          <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Total deductions</div>
          <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{formatMoney(run.total_deductions)}</div>
        </Card>
        <Card>
          <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Total net</div>
          <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{formatMoney(run.total_net)}</div>
        </Card>
      </div>

      {exceptions.length > 0 && (
        <Card style={{ marginBottom: 20, borderColor: "var(--sf-brick)" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--sf-brick)", marginBottom: 4 }}>
            {exceptions.length} exception{exceptions.length === 1 ? "" : "s"}: zero or negative net pay
          </div>
          <div style={{ fontSize: 12, color: "var(--sf-navy-600)" }}>
            {exceptions.map((l) => employeeNameById.get(l.employee_id ?? "") ?? l.casual_worker_id ?? "Unknown worker").join(", ")}
          </div>
        </Card>
      )}

      <Card style={{ marginBottom: 20, padding: 0 }}>
        <div style={{ padding: "12px 16px 0" }}>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>Payslips</h3>
        </div>
        {!run.lines.length ? (
          <EmptyState compact title="No lines in this run." />
        ) : (
          <Table>
            <thead><tr><Th>Employee / worker</Th><Th>Gross</Th><Th>Deductions</Th><Th>Net</Th><Th>Bank ref</Th></tr></thead>
            <tbody>
              {run.lines.map((line) => (
                <PayslipRow key={line.id} line={line} employeeName={line.employee_id ? employeeNameById.get(line.employee_id) : undefined} />
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <BankExportCard run={run} employeeNameById={employeeNameById} />
        <FinancePostingCard run={run} />
      </div>

      {run.status !== "finalized" && (
        <Card style={{ marginTop: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 8 }}>Finalize</h3>
          <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
            Closes this run for further changes. Review payslips and exceptions above first.
          </p>
          {finalizeError && <ErrorBanner title="Could not finalize" detail={finalizeError} onDismiss={() => setFinalizeError(null)} />}
          <Button onClick={handleFinalize} disabled={finalize.isPending}>
            {finalize.isPending ? "Finalizing…" : "Finalize payroll run"}
          </Button>
        </Card>
      )}
    </div>
  );
}

function PayslipRow({ line, employeeName }: { line: PayrollLine; employeeName?: string }) {
  return (
    <tr>
      <Td>{employeeName ?? (line.casual_worker_id ? "Casual worker" : "Unknown")}</Td>
      <Td mono>{formatMoney(line.gross_pay)}</Td>
      <Td mono>{formatMoney(line.total_deductions)}</Td>
      <Td mono><strong>{formatMoney(line.net_pay)}</strong></Td>
      <Td>{line.bank_account_ref || "—"}</Td>
    </tr>
  );
}

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** Real CSV bank export -- client-side, generated from the run's own
 * real lines (gross/net/bank_account_ref, now exposed on the
 * schema). No real bank-specific file format (e.g. NIBSS) is
 * implemented -- this batch's brief says "where existing architecture
 * supports it," and a generic CSV of amount + bank reference is what
 * this backend's real data honestly supports; a bank-specific format
 * would need real, bank-specific field mapping this batch doesn't
 * have. See docs/WFM_SUB_GAPS.md. */
function BankExportCard({ run, employeeNameById }: { run: import("./hooks").PayrollRun; employeeNameById: Map<string, string> }) {
  function handleExport() {
    const header = "Name,Bank Reference,Net Pay";
    const rows = run.lines.map((l) => {
      const name = l.employee_id ? employeeNameById.get(l.employee_id) ?? "" : "Casual worker";
      return [csvCell(name), csvCell(l.bank_account_ref ?? ""), l.net_pay].join(",");
    });
    const csv = [header, ...rows].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `payroll-${run.period_start}-bank-export.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const hasBankRefs = run.lines.some((l) => l.bank_account_ref);

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 4 }}>Bank export</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        A generic CSV of name, bank reference, and net pay for every line in this run.
      </p>
      {!hasBankRefs && (
        <p style={{ fontSize: 12, color: "var(--sf-amber)", marginBottom: 12 }}>
          No lines have a bank reference on file yet — the export will still work, with those fields blank.
        </p>
      )}
      <Button variant="secondary" onClick={handleExport} disabled={!run.lines.length}>
        Export CSV
      </Button>
    </Card>
  );
}

function FinancePostingCard({ run }: { run: import("./hooks").PayrollRun }) {
  const postToFinance = usePostPayrollToFinance();
  const [companyId, setCompanyId] = useState("");
  const [expenseAccountId, setExpenseAccountId] = useState("");
  const [payableAccountId, setPayableAccountId] = useState("");
  const [description, setDescription] = useState(`Payroll ${run.period_start} to ${run.period_end}`);
  const [error, setError] = useState<string | null>(null);
  const [posted, setPosted] = useState(false);

  async function handlePost() {
    setError(null);
    try {
      await postToFinance.mutateAsync({
        company_id: companyId,
        expense_account_id: expenseAccountId,
        payable_account_id: payableAccountId,
        description,
        total_gross: run.total_gross,
      });
      setPosted(true);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card>
      <h3 style={{ fontSize: 14, marginBottom: 4 }}>Post to finance</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        Records the real gross payroll liability as a journal entry (debit expense, credit wages payable).
      </p>
      {posted ? (
        <div style={{ fontSize: 13, color: "var(--sf-green)" }}>Posted to finance.</div>
      ) : (
        <>
          <Field label="Company"><CompanySelect value={companyId} onChange={setCompanyId} /></Field>
          <Field label="Expense account (debit)"><AccountSelect value={expenseAccountId} onChange={setExpenseAccountId} /></Field>
          <Field label="Wages payable account (credit)"><AccountSelect value={payableAccountId} onChange={setPayableAccountId} /></Field>
          <Field label="Description"><Input value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
          {error && <ErrorBanner title="Could not post to finance" detail={error} onDismiss={() => setError(null)} />}
          <Button onClick={handlePost} disabled={!companyId || !expenseAccountId || !payableAccountId || postToFinance.isPending}>
            {postToFinance.isPending ? "Posting…" : "Post"}
          </Button>
        </>
      )}
    </Card>
  );
}
