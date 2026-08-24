import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader, Button, Card, Badge, Field, Input } from "../../components/ui";
import { DataTable } from "../../components/DataTable";
import { QueryState } from "../../components/QueryState";
import { Modal } from "../../components/Modal";
import { useTenders, useCreateTender } from "./hooks";
import type { Tender } from "./types";
import { useToast } from "../../lib/toast";
import { getErrorMessage, getFieldErrors } from "../../api/client";
import { useUnsavedChanges } from "../../lib/useUnsavedChanges";

function statusTone(status: string): "green" | "amber" | "neutral" | "brick" {
  if (status === "won") return "green";
  if (status === "lost") return "brick";
  if (status === "submitted") return "amber";
  return "neutral";
}

function CreateTenderModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const create = useCreateTender();
  const [opportunityId, setOpportunityId] = useState("");
  const [referenceNumber, setReferenceNumber] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const isDirty = opportunityId.trim() !== "" || referenceNumber.trim() !== "";
  useUnsavedChanges(isDirty && !create.isPending);

  async function submit() {
    const errors: Record<string, string> = {};
    if (!opportunityId.trim()) errors.opportunityId = "Opportunity ID is required.";
    if (!referenceNumber.trim()) errors.referenceNumber = "Reference number is required.";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setFormError(null);
    try {
      await create.mutateAsync({ opportunity_id: opportunityId.trim(), reference_number: referenceNumber.trim() });
      toast.success(`Tender "${referenceNumber.trim()}" was created.`);
      onDone();
    } catch (err) {
      setFieldErrors(Object.fromEntries(getFieldErrors(err).map((f) => [f.field, f.message])));
      setFormError(getErrorMessage(err));
    }
  }

  return (
    <Modal title="Create Tender" onClose={onClose} confirmCloseIfDirty={isDirty && !create.isPending}>
      <Field label="Opportunity ID" required error={fieldErrors.opportunityId}>
        <Input value={opportunityId} onChange={(e) => setOpportunityId(e.target.value)} placeholder="Opportunity UUID" />
      </Field>
      <Field label="Reference number" required error={fieldErrors.referenceNumber}>
        <Input value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} placeholder="e.g. TND-2026-014" />
      </Field>
      {formError && (
        <div role="alert" style={{ color: "var(--sf-brick)", fontSize: 12, marginTop: 4 }}>
          {formError}
        </div>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <Button variant="secondary" onClick={onClose} disabled={create.isPending}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={create.isPending}>
          {create.isPending ? "Creating…" : "Create Tender"}
        </Button>
      </div>
    </Modal>
  );
}

export default function TendersPage() {
  const query = useTenders();
  const [showCreate, setShowCreate] = useState(false);

  const columns = useMemo(
    () => [
      { key: "reference", header: "Reference", render: (t: Tender) => t.reference_number, sortValue: (t: Tender) => t.reference_number },
      { key: "status", header: "Status", render: (t: Tender) => <Badge tone={statusTone(t.status)}>{t.status}</Badge>, sortValue: (t: Tender) => t.status },
      { key: "due", header: "Due date", render: (t: Tender) => <span className="sf-mono">{t.submission_deadline || "—"}</span>, sortValue: (t: Tender) => t.submission_deadline ?? "" },
    ],
    []
  );

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader eyebrow="Tender Management" title="Tenders" action={<Button onClick={() => setShowCreate(true)}>+ New Tender</Button>} />

      <Card style={{ padding: query.isLoading || query.isError ? 0 : undefined }}>
        <QueryState
          query={query}
          variant="table"
          loadingLabel="Loading tenders"
          emptyTitle="No tenders yet"
          emptyHint="Create a tender once an opportunity is ready to bid."
          emptyAction={<Button onClick={() => setShowCreate(true)}>+ New Tender</Button>}
        >
          {(tenders: Tender[]) => (
            <DataTable
              columns={columns}
              rows={tenders}
              getRowId={(t) => t.id}
              searchFields={(t) => [t.reference_number, t.status]}
              searchPlaceholder="Search tenders…"
              exportFilename="tenders"
              emptyTitle="No tenders match your search"
              rowActions={(t) => (
                <Link to={`/tenders/${t.id}`}>
                  <Button variant="ghost">View</Button>
                </Link>
              )}
            />
          )}
        </QueryState>
      </Card>

      {showCreate && <CreateTenderModal onClose={() => setShowCreate(false)} onDone={() => setShowCreate(false)} />}
    </div>
  );
}
