import { Link, useParams } from "react-router-dom";
import { Badge, Card, EmptyState, ErrorBanner, formatMoney, Table, Td, Th } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useMyAgreements, useScopeItems } from "./hooks";
import { toneFor } from "./format";

export default function AgreementDetailPage() {
  const { agreementId } = useParams<{ agreementId: string }>();
  const { data: agreements, isLoading } = useMyAgreements();
  const { data: items, isLoading: loadingItems, error } = useScopeItems(agreementId);

  if (isLoading) return <p>Loading…</p>;
  // Resolving from the subcontractor's own agreements doubles as an ownership guard in the UI.
  const agreement = agreements?.find((a) => a.id === agreementId);
  if (!agreement) {
    return (
      <div>
        <EmptyState title="Agreement not found" hint="It may not belong to your organization." />
        <p style={{ marginTop: 12 }}><Link to="/subcontractor-portal/agreements">← Back to agreements</Link></p>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <Link to="/subcontractor-portal/agreements" style={{ fontSize: 12 }}>← All agreements</Link>

      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
          <div>
            <div className="sf-mono" style={{ fontSize: 11, textTransform: "uppercase", color: "var(--sf-navy-400)" }}>Agreement</div>
            <h2 className="sf-mono" style={{ fontSize: 20, margin: "4px 0 0" }}>{agreement.agreement_number}</h2>
          </div>
          <Badge tone={toneFor(agreement.status)}>{agreement.status}</Badge>
        </div>
        <dl style={{ display: "grid", gridTemplateColumns: "160px 1fr", rowGap: 8, fontSize: 13, margin: "16px 0 0" }}>
          <dt style={{ color: "var(--sf-navy-400)" }}>Contract value</dt>
          <dd className="sf-mono" style={{ margin: 0 }}>{formatMoney(agreement.value, agreement.currency)}</dd>
          <dt style={{ color: "var(--sf-navy-400)" }}>Retention</dt>
          <dd className="sf-mono" style={{ margin: 0 }}>{parseFloat(agreement.retention_percentage)}%</dd>
          <dt style={{ color: "var(--sf-navy-400)" }}>Payment terms</dt>
          <dd style={{ margin: 0 }}>{agreement.payment_terms_summary || "—"}</dd>
        </dl>
      </Card>

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Scope of work</h3>
        {error ? (
          <ErrorBanner title="Couldn't load scope items" detail={getErrorMessage(error)} />
        ) : loadingItems ? (
          <p>Loading…</p>
        ) : !items?.length ? (
          <EmptyState title="No scope items recorded" />
        ) : (
          <Table>
            <thead><tr><Th>Description</Th><Th>Basis</Th><Th>Quantity</Th><Th>Rate</Th><Th>Amount</Th></tr></thead>
            <tbody>
              {items.map((i) => {
                const amount = i.is_lump_sum ? i.lump_sum_amount : i.quantity && i.rate ? parseFloat(i.quantity) * parseFloat(i.rate) : null;
                return (
                  <tr key={i.id}>
                    <Td style={{ maxWidth: 360 }}>{i.description}</Td>
                    <Td>{i.is_lump_sum ? "Lump sum" : "Unit rate"}</Td>
                    <Td mono>{i.is_lump_sum ? "—" : `${parseFloat(i.quantity ?? "0")} ${i.unit ?? ""}`}</Td>
                    <Td mono>{i.is_lump_sum ? "—" : formatMoney(i.rate, agreement.currency)}</Td>
                    <Td mono>{formatMoney(amount, agreement.currency)}</Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
