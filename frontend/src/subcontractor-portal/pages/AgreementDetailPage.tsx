import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader, Card, Table, Th, Td, Badge, Button, Input, Field, formatMoney } from "../../components/ui";
import { useAgreement, useProgressEntries, submitProgress, usePaymentCertificates, useClaims, submitClaim } from "../hooks";
import type { ClaimType } from "../types";
import { CLAIM_TYPES } from "../types";
import { getSubcontractorPortalErrorMessage } from "../api/client";

function statusTone(status: string): "green" | "amber" | "neutral" | "brick" {
  if (status === "active" || status === "approved" || status === "paid") return "green";
  if (status === "completed" || status === "issued") return "neutral";
  if (status === "terminated" || status === "rejected") return "brick";
  return "amber";
}

/** Progress submission (item 5) -- real, backed by POST
 * /v1/scp/portal-users/<id>/progress-entries. No "percentage
 * complete" field or draft-save capability here: confirmed directly
 * against backend/app/modules/scp/schemas.py's own SubmitProgressSchema
 * that the only real, supported field is submitted_quantity (against
 * an optional scope_item_id) -- there's no separate draft state on
 * SubcontractProgressEntry at all, a submission is final the moment
 * it's created. See docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md. */
function ProgressSection({ agreementId }: { agreementId: string }) {
  const { entries, reload } = useProgressEntries(agreementId);
  const [quantity, setQuantity] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!quantity || Number(quantity) <= 0) {
      setError("Enter a real quantity greater than zero.");
      return;
    }
    setSubmitting(true);
    try {
      await submitProgress({ agreement_id: agreementId, submitted_quantity: quantity });
      setQuantity("");
      reload();
    } catch (err: any) {
      setError(getSubcontractorPortalErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Progress submissions</h3>
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          <Field label="Submitted quantity">
            <Input type="number" step="0.01" value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="0.00" />
          </Field>
        </div>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Submitting…" : "Submit progress"}
        </Button>
      </form>
      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>}

      {!entries || entries.length === 0 ? (
        <p style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>No progress submitted yet.</p>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Quantity</Th>
              <Th>Status</Th>
              <Th>Submitted</Th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id}>
                <Td mono>{e.submitted_quantity}</Td>
                <Td>
                  <Badge tone={statusTone(e.status)}>{e.status}</Badge>
                </Td>
                <Td mono>{new Date(e.submitted_at).toLocaleDateString()}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

/** Certificates (item 7) -- real, read-only, backed by GET
 * /v1/scp/portal-users/<id>/payment-certificates. No
 * download/preview here: confirmed directly against
 * backend/app/modules/sub/models.py's PaymentCertificate that it has
 * no document/file reference at all, only computed monetary fields --
 * there is genuinely nothing to download yet. */
function CertificatesSection({ agreementId }: { agreementId: string }) {
  const { certificates, error } = usePaymentCertificates(agreementId);

  return (
    <Card style={{ marginTop: 16 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Payment certificates</h3>
      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12 }}>{error}</div>}
      {!certificates || certificates.length === 0 ? (
        <p style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>No certificates issued yet.</p>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Certificate</Th>
              <Th>Period</Th>
              <Th>Gross</Th>
              <Th>Retention</Th>
              <Th>Net payable</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {certificates.map((c) => (
              <tr key={c.id}>
                <Td>{c.certificate_number}</Td>
                <Td mono>{c.period_start} – {c.period_end}</Td>
                <Td mono>{formatMoney(c.gross_certified_amount)}</Td>
                <Td mono>{formatMoney(c.retention_withheld)}</Td>
                <Td mono>{formatMoney(c.net_payable)}</Td>
                <Td>
                  <Badge tone={statusTone(c.status)}>{c.status}</Badge>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

/** Claims (item 6) -- real create + list, backed by POST/GET
 * /v1/scp/portal-users/<id>/claims. */
function ClaimsSection({ agreementId }: { agreementId: string }) {
  const { claims, reload } = useClaims(agreementId);
  const [claimType, setClaimType] = useState<ClaimType>("delay");
  const [description, setDescription] = useState("");
  const [claimedAmount, setClaimedAmount] = useState("");
  const [claimedDays, setClaimedDays] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [showForm, setShowForm] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!description.trim()) {
      setError("Describe the claim before submitting.");
      return;
    }
    setSubmitting(true);
    try {
      await submitClaim({
        agreement_id: agreementId,
        claim_type: claimType,
        description,
        claimed_amount: claimedAmount || undefined,
        claimed_days: claimedDays ? Number(claimedDays) : undefined,
      });
      setDescription("");
      setClaimedAmount("");
      setClaimedDays("");
      setShowForm(false);
      reload();
    } catch (err: any) {
      setError(getSubcontractorPortalErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card style={{ marginTop: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600 }}>Claims</h3>
        {!showForm && (
          <Button variant="secondary" onClick={() => setShowForm(true)}>
            + New claim
          </Button>
        )}
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} style={{ marginBottom: 16, padding: 12, background: "var(--sf-paper-dim)", borderRadius: "var(--sf-radius)" }}>
          <Field label="Claim type">
            <select
              value={claimType}
              onChange={(e) => setClaimType(e.target.value as ClaimType)}
              style={{ width: "100%", padding: "8px 10px", borderRadius: "var(--sf-radius)", border: "1px solid var(--sf-line)" }}
            >
              {CLAIM_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Description">
            <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe the claim" />
          </Field>
          <div style={{ display: "flex", gap: 8 }}>
            <div style={{ flex: 1 }}>
              <Field label="Claimed amount (optional)">
                <Input type="number" value={claimedAmount} onChange={(e) => setClaimedAmount(e.target.value)} placeholder="0.00" />
              </Field>
            </div>
            <div style={{ flex: 1 }}>
              <Field label="Claimed days (optional)">
                <Input type="number" value={claimedDays} onChange={(e) => setClaimedDays(e.target.value)} placeholder="0" />
              </Field>
            </div>
          </div>
          {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 12 }}>{error}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Submitting…" : "Submit claim"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {!claims || claims.length === 0 ? (
        <p style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>No claims submitted yet.</p>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Type</Th>
              <Th>Description</Th>
              <Th>Amount</Th>
              <Th>Status</Th>
              <Th>Submitted</Th>
            </tr>
          </thead>
          <tbody>
            {claims.map((c) => (
              <tr key={c.id}>
                <Td>{c.claim_type.replace(/_/g, " ")}</Td>
                <Td>{c.description}</Td>
                <Td mono>{c.claimed_amount ? formatMoney(c.claimed_amount) : "—"}</Td>
                <Td>
                  <Badge tone={statusTone(c.status)}>{c.status}</Badge>
                </Td>
                <Td mono>{new Date(c.submitted_at).toLocaleDateString()}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

export default function AgreementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { agreement, error, loading } = useAgreement(id);

  if (loading) return <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>;
  if (error) return <div style={{ padding: 32, color: "var(--sf-brick)" }}>{error}</div>;
  if (!agreement) return null;

  return (
    <div>
      <PageHeader eyebrow="Agreement" title={agreement.agreement_number} />

      <Card>
        <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20 }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Value</div>
            <div className="sf-mono" style={{ fontSize: 16, fontWeight: 600 }}>{formatMoney(agreement.value, agreement.currency)}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Retention</div>
            <div>{agreement.retention_percentage}%</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Status</div>
            <Badge tone={statusTone(agreement.status)}>{agreement.status}</Badge>
          </div>
        </div>
        {agreement.payment_terms_summary && (
          <p style={{ fontSize: 13, color: "var(--sf-navy-600)", marginTop: 16 }}>{agreement.payment_terms_summary}</p>
        )}
      </Card>

      {id && <ProgressSection agreementId={id} />}
      {id && <CertificatesSection agreementId={id} />}
      {id && <ClaimsSection agreementId={id} />}
    </div>
  );
}
