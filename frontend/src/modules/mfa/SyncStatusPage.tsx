import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input } from "../../components/ui";
import { useSyncStatus, useConflicts, useResolveConflict } from "./hooks";

export default function SyncStatusPage() {
  const { data: status } = useSyncStatus();
  const { data: conflicts, isLoading } = useConflicts("unresolved");
  const resolveConflict = useResolveConflict();
  const [decisions, setDecisions] = useState<Record<string, string>>({});

  return (
    <div>
      <PageHeader eyebrow="Mobile Field App" title="Sync Status & Conflicts" />

      {status && (
        <div style={{ display: "flex", gap: 20, marginBottom: 20 }}>
          {(["pending", "synced", "conflict", "rejected"] as const).map((key) => (
            <Card key={key} style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>{key}</div>
              <div className="sf-mono" style={{ fontSize: 24, fontWeight: 700 }}>{status[key] ?? 0}</div>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <h3 style={{ fontSize: 14, marginBottom: 4 }}>Unresolved conflicts</h3>
        <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
          Every offline-captured record that couldn't apply cleanly lands here — never silently dropped, with the
          original client payload preserved for review.
        </p>
        {isLoading ? (
          <p>Loading…</p>
        ) : !conflicts?.length ? (
          <EmptyState title="No unresolved conflicts" hint="Offline records that fail to sync cleanly will appear here for review." />
        ) : (
          <Table>
            <thead><tr><Th>Type</Th><Th>Client payload</Th><Th></Th></tr></thead>
            <tbody>
              {conflicts.map((c: any) => (
                <tr key={c.id}>
                  <Td><Badge tone="brick">{c.conflict_type.replace(/_/g, " ")}</Badge></Td>
                  <Td mono style={{ fontSize: 11, maxWidth: 300, whiteSpace: "normal", wordBreak: "break-word" }}>
                    {JSON.stringify(c.client_payload)}
                  </Td>
                  <Td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <Input
                        placeholder="Resolution note"
                        value={decisions[c.id] || ""}
                        onChange={(e) => setDecisions({ ...decisions, [c.id]: e.target.value })}
                        style={{ width: 140, fontSize: 11 }}
                      />
                      <Button
                        variant="secondary"
                        disabled={!decisions[c.id] || resolveConflict.isPending}
                        onClick={() => resolveConflict.mutate({ conflictId: c.id, resolution: { decision: decisions[c.id] } })}
                      >
                        Resolve
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
