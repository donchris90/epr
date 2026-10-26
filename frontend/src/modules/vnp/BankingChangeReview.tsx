import { Fragment, useState } from "react";
import { Card, Button, Table, Th, Td, EmptyState, Input, Badge, ErrorBanner } from "../../components/ui";
import { useBankingChangeRequests, useApproveBankingChange, useRejectBankingChange } from "./hooks";

type Details = Record<string, unknown> | null | undefined;

interface Row {
  id: string;
  vendor_id: string;
  vendor_name: string | null;
  status: "pending" | "approved" | "rejected";
  submitted_at: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  proposed_banking_details: Record<string, unknown>;
  current_banking_details: Details;
  previous_banking_details: Details;
}

function errorText(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

const show = (v: unknown) => (v === undefined || v === null || v === "" ? "—" : String(v));

/** Field-by-field comparison of what the vendor has on file against
 * what they are asking for. Changed fields are marked, because a payment
 * detail change is exactly where a reviewer needs to see what differs. */
export function DetailsDiff({ before, after, beforeLabel }: { before: Details; after: Details; beforeLabel: string }) {
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]));
  return (
    <Table>
      <thead>
        <tr>
          <Th>Field</Th>
          <Th>{beforeLabel}</Th>
          <Th>Proposed</Th>
        </tr>
      </thead>
      <tbody>
        {keys.map((k) => {
          const b = before?.[k];
          const a = after?.[k];
          const changed = show(b) !== show(a);
          return (
            <tr key={k} data-changed={changed ? "true" : "false"}>
              <Td>{k.replace(/_/g, " ")}</Td>
              <Td mono>{show(b)}</Td>
              <Td mono style={changed ? { fontWeight: 700, color: "var(--sf-brick)" } : undefined}>
                {show(a)}
                {changed && " ●"}
              </Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}

function PendingCard({ r }: { r: Row }) {
  const approve = useApproveBankingChange();
  const reject = useRejectBankingChange();
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState(false);
  const error = approve.error || reject.error;

  return (
    <Card style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h4 style={{ fontSize: 14, fontWeight: 600 }}>{r.vendor_name ?? `Vendor ${r.vendor_id.slice(0, 8)}…`}</h4>
        <span style={{ fontSize: 12, color: "var(--sf-navy-400)" }}>
          {r.submitted_at ? `Submitted ${new Date(r.submitted_at).toLocaleString()}` : ""}
        </span>
      </div>
      <div style={{ marginTop: 8 }}>
        <DetailsDiff before={r.current_banking_details} after={r.proposed_banking_details} beforeLabel="On file now" />
      </div>
      {!r.current_banking_details && (
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 6 }}>
          This vendor has no banking details on file yet.
        </p>
      )}
      {error && <ErrorBanner title="Could not complete that action" detail={errorText(error)} />}
      <p style={{ fontSize: 12, color: "var(--sf-navy-600)", marginTop: 10 }}>
        Approving replaces the details used for payment. Confirm the change with the vendor through a channel you
        already trust, not one supplied in the request.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
        {confirming ? (
          <>
            <Button onClick={() => approve.mutate(r.id)} disabled={approve.isPending}>
              {approve.isPending ? "Approving…" : "Confirm approval"}
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <Button onClick={() => setConfirming(true)}>Approve</Button>
        )}
        <Input
          aria-label={`Rejection reason for ${r.vendor_name ?? r.id}`}
          placeholder="Rejection reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          style={{ width: 200 }}
        />
        <Button
          variant="ghost"
          disabled={!reason.trim() || reject.isPending}
          onClick={() => reject.mutate({ requestId: r.id, reason: reason.trim() })}
        >
          Reject
        </Button>
      </div>
    </Card>
  );
}

function HistoryTable({ rows }: { rows: Row[] }) {
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <Table>
      <thead>
        <tr>
          <Th>Vendor</Th>
          <Th>Decision</Th>
          <Th>Decided</Th>
          <Th />
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <Fragment key={r.id}>
            <tr>
              <Td>{r.vendor_name ?? r.vendor_id.slice(0, 8)}</Td>
              <Td>
                <Badge tone={r.status === "approved" ? "green" : "brick"}>{r.status}</Badge>
                {r.rejection_reason && <span style={{ fontSize: 12, marginLeft: 8 }}>{r.rejection_reason}</span>}
              </Td>
              <Td>{r.reviewed_at ? new Date(r.reviewed_at).toLocaleString() : "—"}</Td>
              <Td style={{ textAlign: "right" }}>
                <button
                  onClick={() => setOpenId(openId === r.id ? null : r.id)}
                  style={{ background: "none", border: "none", color: "var(--sf-steel)", cursor: "pointer", fontSize: 12 }}
                >
                  {openId === r.id ? "Hide" : "Details"}
                </button>
              </Td>
            </tr>
            {openId === r.id && (
              <tr>
                <td colSpan={4} style={{ padding: "10px 12px", borderBottom: "1px solid var(--sf-line)" }}>
                  {r.status === "approved" ? (
                    <DetailsDiff before={r.previous_banking_details} after={r.proposed_banking_details} beforeLabel="Replaced" />
                  ) : (
                    <DetailsDiff before={r.current_banking_details} after={r.proposed_banking_details} beforeLabel="On file" />
                  )}
                </td>
              </tr>
            )}
          </Fragment>
        ))}
      </tbody>
    </Table>
  );
}

export default function BankingChangeReview() {
  const [tab, setTab] = useState<"pending" | "history">("pending");
  const pending = useBankingChangeRequests("pending");
  const all = useBankingChangeRequests("all");
  const history: Row[] = ((all.data as Row[]) ?? []).filter((r) => r.status !== "pending");
  const pendingRows = (pending.data as Row[]) ?? [];

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Button variant={tab === "pending" ? undefined : "ghost"} onClick={() => setTab("pending")}>
          Pending ({pendingRows.length})
        </Button>
        <Button variant={tab === "history" ? undefined : "ghost"} onClick={() => setTab("history")}>
          History
        </Button>
      </div>
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
        A vendor-submitted change never touches the live vendor record. It takes explicit approval here, held behind a
        permission a vendor-portal session can never have.
      </p>
      {tab === "pending" ? (
        pending.isLoading ? (
          <p>Loading…</p>
        ) : pending.isError ? (
          <ErrorBanner title="Could not load requests" detail={errorText(pending.error)} />
        ) : !pendingRows.length ? (
          <EmptyState title="Nothing pending" hint="Banking detail changes submitted through the vendor portal appear here for review." />
        ) : (
          pendingRows.map((r) => <PendingCard key={r.id} r={r} />)
        )
      ) : all.isLoading ? (
        <p>Loading…</p>
      ) : !history.length ? (
        <EmptyState title="No decisions yet" hint="Approved and rejected requests will be listed here." />
      ) : (
        <Card style={{ padding: 0 }}>
          <HistoryTable rows={history} />
        </Card>
      )}
    </div>
  );
}
