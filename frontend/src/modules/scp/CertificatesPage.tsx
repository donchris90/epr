import { Fragment, useState } from "react";
import { Badge, Card, EmptyState, ErrorBanner, formatMoney, Table, Td, Th } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useMyAgreements, usePaymentCertificates } from "./hooks";
import { useScpStore } from "./store";
import { fmtDate, num, toneFor } from "./format";

export default function CertificatesPage() {
  const agreementId = useScpStore((s) => s.agreementId);
  const { data: agreements } = useMyAgreements();
  const currency = agreements?.find((a) => a.id === agreementId)?.currency;
  const { data: certs, isLoading, error } = usePaymentCertificates(agreementId);
  const [open, setOpen] = useState<string | null>(null);

  if (!agreementId) return <EmptyState title="Select an agreement" />;
  if (error) return <ErrorBanner title="Couldn't load certificates" detail={getErrorMessage(error)} />;
  if (isLoading) return <p>Loading…</p>;
  if (!certs?.length) return <EmptyState title="No payment certificates issued" hint="Certificates appear here once the contractor issues them." />;

  const sorted = [...certs].sort((a, b) => b.period_end.localeCompare(a.period_end));
  const totalNet = sorted.reduce((s, c) => s + num(c.net_payable), 0);

  return (
    <Card>
      <Table>
        <thead>
          <tr><Th>Certificate</Th><Th>Period</Th><Th>Gross certified</Th><Th>Net payable</Th><Th>Issued</Th><Th>Status</Th></tr>
        </thead>
        <tbody>
          {sorted.map((c) => {
            const isOpen = open === c.id;
            const computedNet = num(c.gross_certified_amount) - num(c.retention_withheld) - num(c.back_charges_total);
            const reconciles = Math.abs(computedNet - num(c.net_payable)) < 0.01;
            return (
              <Fragment key={c.id}>
                <tr onClick={() => setOpen(isOpen ? null : c.id)} style={{ cursor: "pointer" }} aria-expanded={isOpen}>
                  <Td mono>{isOpen ? "▾" : "▸"} {c.certificate_number}</Td>
                  <Td>{fmtDate(c.period_start)} – {fmtDate(c.period_end)}</Td>
                  <Td mono>{formatMoney(c.gross_certified_amount, currency)}</Td>
                  <Td mono>{formatMoney(c.net_payable, currency)}</Td>
                  <Td>{fmtDate(c.issued_at)}</Td>
                  <Td><Badge tone={toneFor(c.status)}>{c.status}</Badge></Td>
                </tr>
                {isOpen && (
                  <tr>
                    <Td style={{ background: "var(--sf-paper)" }} />
                    <Td style={{ background: "var(--sf-paper)" }} />
                    <td colSpan={4} style={{ background: "var(--sf-paper)", padding: "10px 12px", borderBottom: "1px solid var(--sf-line)" }}>
                      <dl className="sf-mono" style={{ display: "grid", gridTemplateColumns: "180px 160px", rowGap: 4, fontSize: 12, margin: 0 }}>
                        <dt>Gross certified</dt><dd style={{ margin: 0, textAlign: "right" }}>{formatMoney(c.gross_certified_amount, currency)}</dd>
                        <dt>Less retention</dt><dd style={{ margin: 0, textAlign: "right" }}>− {formatMoney(c.retention_withheld, currency)}</dd>
                        <dt>Less back-charges</dt><dd style={{ margin: 0, textAlign: "right" }}>− {formatMoney(c.back_charges_total, currency)}</dd>
                        <dt style={{ fontWeight: 600, borderTop: "1px solid var(--sf-line)", paddingTop: 4 }}>Net payable</dt>
                        <dd style={{ margin: 0, textAlign: "right", fontWeight: 600, borderTop: "1px solid var(--sf-line)", paddingTop: 4 }}>{formatMoney(c.net_payable, currency)}</dd>
                      </dl>
                      {!reconciles && (
                        <p style={{ fontSize: 11, color: "var(--sf-brick)", marginTop: 8 }}>
                          These components don't add up to the stated net payable — please query this certificate with the contractor.
                        </p>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </Table>
      <div className="sf-mono" style={{ textAlign: "right", fontSize: 12, marginTop: 12, color: "var(--sf-navy-600)" }}>
        Total net certified: {formatMoney(totalNet, currency)}
      </div>
    </Card>
  );
}
