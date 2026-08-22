import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageHeader, Card, Badge, Button, Select, EmptyState, formatMoney } from "../../components/ui";
import { LoadingState } from "../../components/Loading";
import { ErrorState } from "../../components/ErrorState";
import { useClients, useLead, useConvertLead, useOpportunities } from "./hooks";
import { useToast } from "../../lib/toast";
import { getErrorMessage } from "../../api/client";

/** Same backend gap as ClientDetailPage: no `GET /bdc/leads/<id>`, so
 * this looks the lead up client-side from the full list. There's also
 * no PATCH/DELETE for Lead, so the only action available here (beyond
 * viewing) is the real one the backend supports: convert-to-opportunity. */
export default function LeadDetailPage() {
  const { leadId } = useParams<{ leadId: string }>();
  const lead = useLead(leadId);
  const clients = useClients();
  const opportunities = useOpportunities();
  const convertLead = useConvertLead();
  const toast = useToast();
  const [convertClientId, setConvertClientId] = useState("");

  if (lead.isLoading) {
    return (
      <div>
        <PageHeader eyebrow="Business Development" title="Lead" />
        <LoadingState variant="detail" label="Loading lead" />
      </div>
    );
  }

  if (lead.isError) {
    return (
      <div>
        <PageHeader eyebrow="Business Development" title="Lead" />
        <ErrorState error={lead.error} onRetry={() => lead.refetch()} />
      </div>
    );
  }

  if (!lead.data) {
    return (
      <div>
        <PageHeader eyebrow="Business Development" title="Lead not found" />
        <EmptyState title="Lead not found" hint="It may have been removed, or the link is out of date." />
      </div>
    );
  }

  const l = lead.data;
  const relatedClient = clients.data?.find((c) => c.id === l.client_id);
  const convertedOpportunity = opportunities.data?.find((o) => o.lead_id === l.id);

  async function handleConvert() {
    if (!convertClientId || !leadId) return;
    try {
      await convertLead.mutateAsync({ leadId, clientId: convertClientId });
      toast.success("Lead converted to an opportunity.");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div style={{ maxWidth: 800 }}>
      <PageHeader eyebrow="Business Development · Lead" title={l.name} action={<Badge tone={l.status === "open" ? "steel" : "neutral"}>{l.status}</Badge>} />

      <Card style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--sf-navy-400)", marginBottom: 10 }}>DETAILS</div>
        <dl style={{ fontSize: 13, margin: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--sf-line)" }}>
            <dt style={{ color: "var(--sf-navy-400)" }}>Source</dt>
            <dd style={{ margin: 0 }}>{l.source || "—"}</dd>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--sf-line)" }}>
            <dt style={{ color: "var(--sf-navy-400)" }}>Estimated value</dt>
            <dd style={{ margin: 0 }} className="sf-mono">
              {formatMoney(l.estimated_value, l.currency)}
            </dd>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--sf-line)" }}>
            <dt style={{ color: "var(--sf-navy-400)" }}>Win probability</dt>
            <dd style={{ margin: 0 }}>{l.probability_pct ? `${l.probability_pct}%` : "—"}</dd>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
            <dt style={{ color: "var(--sf-navy-400)" }}>Logged</dt>
            <dd style={{ margin: 0 }} className="sf-mono">
              {new Date(l.created_at).toLocaleDateString()}
            </dd>
          </div>
        </dl>
        <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 12 }}>
          Editing isn't available yet — there's no update endpoint for leads on this backend.
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--sf-navy-400)", marginBottom: 10 }}>CLIENT</div>
        {relatedClient ? (
          <Link to={`/business-development/clients/${relatedClient.id}`} style={{ fontSize: 14, fontWeight: 600 }}>
            {relatedClient.name}
          </Link>
        ) : (
          <div style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>No client linked to this lead yet.</div>
        )}
      </Card>

      <Card>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--sf-navy-400)", marginBottom: 10 }}>CONVERSION</div>
        {convertedOpportunity ? (
          <div>
            <div style={{ fontSize: 13, marginBottom: 6 }}>This lead has been converted to an opportunity:</div>
            <Link to={`/business-development/opportunities/${convertedOpportunity.id}`} style={{ fontSize: 14, fontWeight: 600 }}>
              {convertedOpportunity.name} →
            </Link>
          </div>
        ) : l.status === "open" ? (
          <div>
            <div style={{ fontSize: 13, color: "var(--sf-navy-400)", marginBottom: 10 }}>
              Converting creates an Opportunity from this lead and marks it converted. Choose the client this opportunity belongs to.
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <Select value={convertClientId} onChange={(e) => setConvertClientId(e.target.value)} aria-label="Select client">
                <option value="">Select client…</option>
                {clients.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
              <Button onClick={handleConvert} disabled={!convertClientId || convertLead.isPending}>
                {convertLead.isPending ? "Converting…" : "Convert to opportunity"}
              </Button>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>This lead is {l.status} and can't be converted.</div>
        )}
      </Card>
    </div>
  );
}
