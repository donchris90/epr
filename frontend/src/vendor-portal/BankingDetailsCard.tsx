import { useState } from "react";
import { Badge, Button, Card, Field, Input } from "../components/ui";
import { getVendorPortalErrorMessage } from "./api/client";
import { submitBankingChange, useBankingChangeRequests } from "./hooks";

/** Last four digits only -- the full number is never shown back. */
export function maskAccount(n?: string): string {
  if (!n) return "—";
  return n.length <= 4 ? n : `••••${n.slice(-4)}`;
}

const TONE: Record<string, "steel" | "green" | "brick"> = { pending: "steel", approved: "green", rejected: "brick" };

/** Vendor-facing half of VNP-05. Submitting does not change the live
 * banking details: the request waits for the contractor's finance team,
 * and the vendor is notified of the decision. */
export default function BankingDetailsCard() {
  const { requests, error: loadError, reload } = useBankingChangeRequests();
  const [bankName, setBankName] = useState("");
  const [accountName, setAccountName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  const pending = requests?.some((r) => r.status === "pending") ?? false;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!/^\d{6,20}$/.test(accountNumber.trim())) {
      setError("Account number must be 6–20 digits.");
      return;
    }
    setSubmitting(true);
    try {
      await submitBankingChange({ bank_name: bankName.trim(), account_name: accountName.trim(), account_number: accountNumber.trim() });
      setSent(true);
      setBankName("");
      setAccountName("");
      setAccountNumber("");
      reload();
    } catch (err: any) {
      setError(getVendorPortalErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Bank details</h3>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 16 }}>
        Payments go to the account on file. A change is reviewed by the contractor's finance team before it takes effect.
      </p>

      {pending ? (
        <div style={{ fontSize: 13, color: "var(--sf-navy-600)", marginBottom: 12 }}>
          You have a change awaiting review. You can submit another once it has been decided.
        </div>
      ) : (
        <form onSubmit={handleSubmit} style={{ marginBottom: 16 }}>
          {sent && <div style={{ fontSize: 12, color: "var(--sf-green)", marginBottom: 10 }}>Submitted for review.</div>}
          <Field label="Bank name">
            <Input required value={bankName} onChange={(e) => setBankName(e.target.value)} />
          </Field>
          <Field label="Account name">
            <Input required value={accountName} onChange={(e) => setAccountName(e.target.value)} />
          </Field>
          <Field label="Account number">
            <Input required inputMode="numeric" value={accountNumber} onChange={(e) => setAccountNumber(e.target.value)} />
          </Field>
          {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Submitting…" : "Request change"}
          </Button>
        </form>
      )}

      {loadError && <div style={{ color: "var(--sf-brick)", fontSize: 12 }}>{loadError}</div>}
      {requests && requests.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>Requests</div>
          {requests.map((r) => (
            <div key={r.id} style={{ borderTop: "1px solid var(--sf-line)", padding: "8px 0", fontSize: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span>
                  {r.proposed_banking_details.bank_name ?? "—"} · {maskAccount(r.proposed_banking_details.account_number)}
                </span>
                <Badge tone={TONE[r.status] ?? "steel"}>{r.status}</Badge>
              </div>
              {r.submitted_at && <div style={{ color: "var(--sf-navy-400)" }}>{new Date(r.submitted_at).toLocaleDateString()}</div>}
              {r.status === "rejected" && r.rejection_reason && (
                <div style={{ color: "var(--sf-brick)", marginTop: 2 }}>Reason: {r.rejection_reason}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
