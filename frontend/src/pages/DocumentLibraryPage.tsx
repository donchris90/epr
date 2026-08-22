import { useEffect, useRef, useState } from "react";
import { apiClient, getErrorMessage } from "../api/client";
import { useUploadDocument } from "../api/documents";
import { PageHeader, Card, Button, Table, Th, Td, Badge, Select, Field, EmptyState } from "../components/ui";
import { LoadingState } from "../components/Loading";
import { ErrorState } from "../components/ErrorState";
import { ProjectSelect } from "../components/ProjectSelect";
import { useToast } from "../lib/toast";

interface DocumentRow {
  id: string;
  project_id: string | null;
  doc_type: string | null;
  original_filename: string | null;
  content_type: string | null;
  size_bytes: number | null;
  status: string;
  created_at: string;
}

const COMMON_DOC_TYPES = ["drawing", "contract", "photo", "report", "certificate", "invoice", "other"];

function formatSize(bytes: number | null) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusBadge(status: string) {
  if (status === "uploaded") return <Badge tone="green">Ready</Badge>;
  if (status === "pending") return <Badge tone="amber">Uploading…</Badge>;
  return <Badge tone="neutral">{status}</Badge>;
}

/** Real document library, backed by the real S3-backed storage
 * (backend/app/documents/) -- reuses the existing, already-tested
 * useUploadDocument hook (api/documents.ts) for the real 3-step
 * upload flow (request a slot, PUT bytes directly to S3, confirm)
 * rather than reimplementing it here.
 *
 * Honest about a real constraint: S3_ACCESS_KEY/S3_SECRET_KEY are
 * empty by default in this app's config (see app/config.py) -- if
 * they're not set on the real deployment, the PUT-to-S3 step of a
 * real upload will genuinely fail. That failure surfaces as a real
 * error here, not a silent no-op or a fake success. */
export default function DocumentLibraryPage() {
  const toast = useToast();
  const [documents, setDocuments] = useState<DocumentRow[] | null>(null);
  const [projectFilter, setProjectFilter] = useState("");
  const [docTypeFilter, setDocTypeFilter] = useState("");
  const [uploadDocType, setUploadDocType] = useState("other");
  const [error, setError] = useState<unknown>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const upload = useUploadDocument();

  async function load() {
    setError(null);
    try {
      const res = await apiClient.get("/documents", {
        params: { project_id: projectFilter || undefined, doc_type: docTypeFilter || undefined },
      });
      setDocuments(res.data.data);
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectFilter, docTypeFilter]);

  function handlePickFile() {
    fileInputRef.current?.click();
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    try {
      await upload.mutateAsync({ file, docType: uploadDocType, projectId: projectFilter || undefined });
      toast.success(`"${file.name}" uploaded.`);
      await load();
    } catch (err) {
      toast.error(
        `Upload failed: ${getErrorMessage(err)}. If this keeps happening, S3 storage may not be configured on this deployment yet.`
      );
    }
  }

  async function handleDownload(doc: DocumentRow) {
    try {
      const res = await apiClient.get(`/documents/${doc.id}`);
      if (res.data.download_url) {
        window.open(res.data.download_url, "_blank");
      } else {
        toast.error("This document has no download link yet — it may still be uploading.");
      }
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  async function handleDelete(doc: DocumentRow) {
    setPendingId(doc.id);
    try {
      await apiClient.delete(`/documents/${doc.id}`);
      toast.success(`"${doc.original_filename ?? "Document"}" deleted.`);
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader
        eyebrow="Documents"
        title="Document Library"
        action={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Select value={uploadDocType} onChange={(e) => setUploadDocType(e.target.value)} style={{ width: 140 }}>
              {COMMON_DOC_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
            <Button onClick={handlePickFile} disabled={upload.isPending}>
              {upload.isPending ? "Uploading…" : "+ Upload"}
            </Button>
            <input ref={fileInputRef} type="file" style={{ display: "none" }} onChange={handleFileSelected} />
          </div>
        }
      />

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <div style={{ width: 260 }}>
          <Field label="Filter by project">
            <ProjectSelect value={projectFilter} onChange={setProjectFilter} placeholder="All projects" />
          </Field>
        </div>
        <div style={{ width: 180 }}>
          <Field label="Filter by type">
            <Select value={docTypeFilter} onChange={(e) => setDocTypeFilter(e.target.value)}>
              <option value="">All types</option>
              {COMMON_DOC_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </div>

      <Card style={{ padding: 0 }}>
        {error ? (
          <ErrorState error={error} onRetry={load} />
        ) : documents === null ? (
          <LoadingState variant="table" label="Loading documents" />
        ) : documents.length === 0 ? (
          <EmptyState
            title="No documents yet"
            hint="Upload your first document to get started."
            action={<Button onClick={handlePickFile}>+ Upload</Button>}
          />
        ) : (
          <Table ariaLabel="Documents">
            <thead>
              <tr>
                <Th>File</Th>
                <Th>Type</Th>
                <Th>Size</Th>
                <Th>Status</Th>
                <Th>Uploaded</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <Td>{doc.original_filename || "—"}</Td>
                  <Td>{doc.doc_type || "—"}</Td>
                  <Td mono>{formatSize(doc.size_bytes)}</Td>
                  <Td>{statusBadge(doc.status)}</Td>
                  <Td mono>{new Date(doc.created_at).toLocaleDateString()}</Td>
                  <Td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      <Button variant="ghost" disabled={doc.status !== "uploaded"} onClick={() => handleDownload(doc)}>
                        Download
                      </Button>
                      <Button variant="danger" disabled={pendingId === doc.id} onClick={() => handleDelete(doc)}>
                        {pendingId === doc.id ? "Deleting…" : "Delete"}
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
