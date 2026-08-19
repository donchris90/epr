import { useState } from "react";
import { PageHeader, Card, Button, Badge, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useCreateExtractionJob, useReviewExtractionJob, useCommitExtractionToBOQ } from "./hooks";

export default function ExtractionPage() {
  const createJob = useCreateExtractionJob();
  const reviewJob = useReviewExtractionJob();
  const commitJob = useCommitExtractionToBOQ();

  const [form, setForm] = useState({ item_code: "", description: "", quantity: "" });
  const [job, setJob] = useState<any>(null);
  const [estimateVersionId, setEstimateVersionId] = useState("");
  const [commitError, setCommitError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const res = await createJob.mutateAsync({
      extraction_type: "boq",
      extracted_data: { item_code: form.item_code, description: form.description, quantity: form.quantity },
      confidence_scores: { item_code: 0.95, description: 0.9, quantity: 0.6 },
    });
    setJob(res.data);
  }

  async function handleReview() {
    const res = await reviewJob.mutateAsync({ jobId: job.id });
    setJob(res.data);
  }

  async function handleCommit(e: React.FormEvent) {
    e.preventDefault();
    setCommitError(null);
    try {
      await commitJob.mutateAsync({ jobId: job.id, estimate_version_id: estimateVersionId });
      setJob({ ...job, status: "committed" });
    } catch (err) {
      // Business rule: extraction never auto-commits -- committing
      // before an explicit review is always rejected here.
      setCommitError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader eyebrow="AI Construction Assistant" title="Document Extraction (BOQ)" />
      <p style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 20, maxWidth: 640 }}>
        Simulates the outcome of an external OCR/LLM extraction step handing structured data to this workflow — the
        actual document-understanding step is out of scope here, but the human-review gate around it is fully real:
        nothing commits to the real BOQ without an explicit review first, regardless of confidence scores.
      </p>

      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, marginBottom: 12 }}>Simulate an extraction</h3>
        <form onSubmit={handleCreate} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr 2fr 1fr auto", gap: 12 }}>
          <Field label="Item code">
            <Input required value={form.item_code} onChange={(e) => setForm({ ...form, item_code: e.target.value })} />
          </Field>
          <Field label="Description">
            <Input required value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <Field label="Quantity">
            <Input required value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </Field>
          <Button type="submit" disabled={createJob.isPending} style={{ height: 38, alignSelf: "end" }}>Extract</Button>
        </form>
      </Card>

      {job && (
        <Card>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <h3 style={{ fontSize: 14 }}>Extraction job</h3>
            <Badge tone={job.status === "committed" ? "green" : job.status === "reviewed" ? "steel" : "amber"}>{job.status}</Badge>
          </div>

          {job.low_confidence_fields?.length > 0 && (
            <div style={{ marginBottom: 12, fontSize: 12, color: "#8a5f14" }}>
              Low-confidence field(s) flagged: {job.low_confidence_fields.join(", ")}
            </div>
          )}

          {commitError && <ErrorBanner title="Cannot commit" detail={commitError} onDismiss={() => setCommitError(null)} />}

          {job.status === "extracted" && (
            <Button variant="secondary" onClick={handleReview} disabled={reviewJob.isPending} style={{ marginBottom: 12 }}>
              {reviewJob.isPending ? "Reviewing…" : "Mark as reviewed"}
            </Button>
          )}

          {job.status === "reviewed" && (
            <form onSubmit={handleCommit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
              <Input required placeholder="Estimate version ID" value={estimateVersionId} onChange={(e) => setEstimateVersionId(e.target.value)} />
              <Button type="submit" disabled={commitJob.isPending}>Commit to BOQ</Button>
            </form>
          )}

          {job.status === "extracted" && (
            <div style={{ marginTop: 12 }}>
              <form onSubmit={handleCommit} className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8 }}>
                <Input required placeholder="Estimate version ID" value={estimateVersionId} onChange={(e) => setEstimateVersionId(e.target.value)} />
                <Button type="submit" disabled={commitJob.isPending} variant="danger">
                  Try commit without review
                </Button>
              </form>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
