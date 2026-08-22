import { Link, useParams } from "react-router-dom";
import { PageHeader, Card, Badge, EmptyState, Table, Th, Td } from "../../components/ui";
import { LoadingState } from "../../components/Loading";
import { ErrorState } from "../../components/ErrorState";
import { useClient, useLeads, useOpportunities } from "./hooks";
import { useTenders } from "../tbm/hooks";

const STAGE_TONE: Record<string, "neutral" | "amber" | "steel" | "green" | "brick"> = {
  identified: "neutral",
  qualified: "steel",
  bid_no_bid: "amber",
  submitted: "amber",
  won: "green",
  lost: "brick",
};

/**
 * There's no `GET /bdc/clients/<id>` endpoint on the backend (only
 * list + create -- see routes.py), so this page has no way to fetch
 * this one client directly. useClient() below finds it in the
 * already-loaded client list instead, and there's no edit/delete
 * capability to offer for the same reason: no PATCH or DELETE route
 * exists for Client at all.
 */
export default function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const client = useClient(clientId);
  const leads = useLeads();
  const opportunities = useOpportunities();
  // Tender has no `opportunity_id` filter param on GET /tbm/tenders
  // (only `status` is supported -- see tbm/routes.py), so "related
  // tenders" for this client is derived client-side: fetch the full
  // tender list and match against the opportunity ids already found
  // for this client below.
  const tenders = useTenders();

  if (client.isLoading || leads.isLoading || opportunities.isLoading) {
    return (
      <div>
        <PageHeader eyebrow="Business Development" title="Client" />
        <LoadingState variant="detail" label="Loading client" />
      </div>
    );
  }

  if (client.isError) {
    return (
      <div>
        <PageHeader eyebrow="Business Development" title="Client" />
        <ErrorState error={client.error} onRetry={() => client.refetch()} />
      </div>
    );
  }

  if (!client.data) {
    return (
      <div>
        <PageHeader eyebrow="Business Development" title="Client not found" />
        <EmptyState title="Client not found" hint="It may have been removed, or the link is out of date." />
      </div>
    );
  }

  const c = client.data;
  const clientLeads = (leads.data ?? []).filter((l) => l.client_id === c.id);
  const clientOpportunities = (opportunities.data ?? []).filter((o) => o.client_id === c.id);
  const opportunityIds = new Set(clientOpportunities.map((o) => o.id));
  const clientTenders = (tenders.data ?? []).filter((t) => opportunityIds.has(t.opportunity_id));

  return (
    <div style={{ maxWidth: 1100 }}>
      <PageHeader eyebrow="Business Development · Client" title={c.name} />

      <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        <Card>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--sf-navy-400)", marginBottom: 10 }}>DETAILS</div>
          <dl style={{ fontSize: 13, margin: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--sf-line)" }}>
              <dt style={{ color: "var(--sf-navy-400)" }}>Billing email</dt>
              <dd style={{ margin: 0 }}>{c.billing_email || "—"}</dd>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--sf-line)" }}>
              <dt style={{ color: "var(--sf-navy-400)" }}>Billing address</dt>
              <dd style={{ margin: 0, textAlign: "right" }}>{c.billing_address || "—"}</dd>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
              <dt style={{ color: "var(--sf-navy-400)" }}>Added</dt>
              <dd style={{ margin: 0 }} className="sf-mono">
                {new Date(c.created_at).toLocaleDateString()}
              </dd>
            </div>
          </dl>
          {c.notes && (
            <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--sf-line)" }}>
              <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 4 }}>Notes</div>
              <div style={{ fontSize: 13 }}>{c.notes}</div>
            </div>
          )}
          <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 12 }}>
            Editing isn't available yet — there's no update endpoint for clients on this backend.
          </div>
        </Card>

        <Card>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--sf-navy-400)", marginBottom: 10 }}>SUMMARY</div>
          <div style={{ display: "flex", gap: 24 }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{clientLeads.length}</div>
              <div style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>Leads</div>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{clientOpportunities.length}</div>
              <div style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>Opportunities</div>
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{clientTenders.length}</div>
              <div style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>Tenders</div>
            </div>
          </div>
        </Card>
      </div>

      <Card style={{ padding: 0, marginBottom: 16 }}>
        <div style={{ padding: "12px 16px", fontWeight: 700, fontSize: 13, borderBottom: "1px solid var(--sf-line)" }}>Leads</div>
        {clientLeads.length === 0 ? (
          <div style={{ padding: 20 }}>
            <EmptyState title="No leads for this client yet" />
          </div>
        ) : (
          <Table ariaLabel="Leads for this client">
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Source</Th>
                <Th>Status</Th>
                <Th>Est. value</Th>
              </tr>
            </thead>
            <tbody>
              {clientLeads.map((l) => (
                <tr key={l.id}>
                  <Td>
                    <Link to={`/business-development/leads/${l.id}`}>{l.name}</Link>
                  </Td>
                  <Td>{l.source || "—"}</Td>
                  <Td>{l.status}</Td>
                  <Td mono>{l.estimated_value ? `${l.currency} ${l.estimated_value}` : "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Card style={{ padding: 0, marginBottom: 16 }}>
        <div style={{ padding: "12px 16px", fontWeight: 700, fontSize: 13, borderBottom: "1px solid var(--sf-line)" }}>Opportunities</div>
        {clientOpportunities.length === 0 ? (
          <div style={{ padding: 20 }}>
            <EmptyState title="No opportunities for this client yet" />
          </div>
        ) : (
          <Table ariaLabel="Opportunities for this client">
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Stage</Th>
                <Th>Est. value</Th>
                <Th>Deadline</Th>
              </tr>
            </thead>
            <tbody>
              {clientOpportunities.map((o) => (
                <tr key={o.id}>
                  <Td>
                    <Link to={`/business-development/opportunities/${o.id}`}>{o.name}</Link>
                  </Td>
                  <Td>
                    <Badge tone={STAGE_TONE[o.stage] ?? "neutral"}>{o.stage.replace(/_/g, " ")}</Badge>
                  </Td>
                  <Td mono>{o.estimated_value ? `${o.currency} ${o.estimated_value}` : "—"}</Td>
                  <Td mono>{o.submission_deadline ? new Date(o.submission_deadline).toLocaleDateString() : "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Card style={{ padding: 0 }}>
        <div style={{ padding: "12px 16px", fontWeight: 700, fontSize: 13, borderBottom: "1px solid var(--sf-line)" }}>
          Related tenders
        </div>
        {tenders.isLoading ? (
          <LoadingState variant="table" label="Loading tenders" rows={2} />
        ) : clientTenders.length === 0 ? (
          <div style={{ padding: 20 }}>
            <EmptyState title="No tenders for this client's opportunities yet" />
          </div>
        ) : (
          <Table ariaLabel="Tenders related to this client">
            <thead>
              <tr>
                <Th>Reference</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {clientTenders.map((t) => (
                <tr key={t.id}>
                  <Td>
                    <Link to={`/tenders/${t.id}`} className="sf-mono">
                      {t.reference_number}
                    </Link>
                  </Td>
                  <Td>{t.status}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
