import { Link } from "react-router-dom";
import { Badge, Card, EmptyState, ErrorBanner, formatMoney, Table, Td, Th } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useMyAgreements, usePortalRollup } from "./hooks";
import { fmtDateTime, humanize, num, toneFor } from "./format";

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <div className="sf-mono" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--sf-navy-400)" }}>{label}</div>
      <div className="sf-mono" style={{ fontSize: 22, fontWeight: 600, marginTop: 6 }}>{value}</div>
      {hint && <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 4 }}>{hint}</div>}
    </Card>
  );
}

export default function DashboardPage() {
  const { data: agreements, isLoading: loadingAgreements, error } = useMyAgreements();
  const ids = (agreements ?? []).map((a) => a.id);
  const { progress, certificates, claims, isLoading, isError } = usePortalRollup(ids);

  if (loadingAgreements) return <p>Loading…</p>;
  if (error) return <ErrorBanner title="Couldn't load agreements" detail={getErrorMessage(error)} />;
  if (!agreements?.length) {
    return <EmptyState title="No agreements yet" hint="Agreements issued to your organization appear here." />;
  }

  const active = agreements.filter((a) => a.status === "active");
  const currency = agreements[0].currency;
  const mixedCurrency = agreements.some((a) => a.currency !== currency);
  const totalValue = agreements.reduce((s, a) => s + num(a.value), 0);
  const netPayable = certificates.reduce((s, c) => s + num(c.net_payable), 0);
  const awaitingVerification = progress.filter((p) => p.status === "submitted").length;
  const openClaims = claims.filter((c) => c.status === "submitted" || c.status === "under_review").length;

  const agreementNo = (id: string) => agreements.find((a) => a.id === id)?.agreement_number ?? id.slice(0, 8);
  const recentCerts = [...certificates].sort((a, b) => (b.issued_at ?? "").localeCompare(a.issued_at ?? "")).slice(0, 5);
  const recentClaims = [...claims].sort((a, b) => b.submitted_at.localeCompare(a.submitted_at)).slice(0, 5);

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {isError && <ErrorBanner title="Some figures couldn't be loaded" detail="Totals below may be incomplete." />}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
        <Stat label="Active agreements" value={String(active.length)} hint={`${agreements.length} in total`} />
        <Stat
          label="Contract value"
          value={mixedCurrency ? "Mixed" : formatMoney(totalValue, currency)}
          hint={mixedCurrency ? "Agreements use different currencies" : undefined}
        />
        <Stat
          label="Certified net payable"
          value={isLoading ? "…" : mixedCurrency ? "Mixed" : formatMoney(netPayable, currency)}
          hint={`${certificates.length} issued certificate${certificates.length === 1 ? "" : "s"}`}
        />
        <Stat label="Progress awaiting review" value={isLoading ? "…" : String(awaitingVerification)} />
        <Stat label="Open claims" value={isLoading ? "…" : String(openClaims)} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", gap: 20 }}>
        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Latest payment certificates</h3>
          {!recentCerts.length ? (
            <EmptyState title="None issued yet" />
          ) : (
            <Table>
              <thead><tr><Th>Certificate</Th><Th>Agreement</Th><Th>Net payable</Th></tr></thead>
              <tbody>
                {recentCerts.map((c) => (
                  <tr key={c.id}>
                    <Td mono>{c.certificate_number}</Td>
                    <Td mono style={{ fontSize: 12 }}>{agreementNo(c.agreement_id)}</Td>
                    <Td mono>{formatMoney(c.net_payable, agreements.find((a) => a.id === c.agreement_id)?.currency)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          <div style={{ marginTop: 12, fontSize: 12 }}><Link to="/subcontractor-portal/certificates">All certificates →</Link></div>
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Latest claims</h3>
          {!recentClaims.length ? (
            <EmptyState title="No claims submitted" />
          ) : (
            <Table>
              <thead><tr><Th>Type</Th><Th>Submitted</Th><Th>Status</Th></tr></thead>
              <tbody>
                {recentClaims.map((c) => (
                  <tr key={c.id}>
                    <Td style={{ textTransform: "capitalize" }}>{humanize(c.claim_type)}</Td>
                    <Td>{fmtDateTime(c.submitted_at)}</Td>
                    <Td><Badge tone={toneFor(c.status)}>{humanize(c.status)}</Badge></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          <div style={{ marginTop: 12, fontSize: 12 }}><Link to="/subcontractor-portal/claims">All claims →</Link></div>
        </Card>
      </div>

      <p style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>Payment figures reflect issued certificates only.</p>
    </div>
  );
}
