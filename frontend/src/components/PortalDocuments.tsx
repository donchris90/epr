import { useCallback, useEffect, useState } from "react";
import type { AxiosInstance } from "axios";
import { Card, Button, Select, Field, Table, Th, Td, ErrorBanner, EmptyState } from "./ui";

/** Shared Documents page for the subcontractor and vendor portals.
 * Uploads go straight to storage with the presigned URL the API hands
 * back; the file never passes through the API server. The portal only
 * ever sees its own organisation's documents. */
export interface PortalDocument {
  id: string;
  doc_type: string | null;
  original_filename: string | null;
  content_type: string | null;
  size_bytes: number | null;
  created_at: string;
}

export interface PortalDocumentsConfig {
  client: Pick<AxiosInstance, "get" | "post">;
  /** e.g. "/vnp/vendor-users/<id>" */
  base: string;
  docTypes: { value: string; label: string }[];
}

export const MAX_UPLOAD_MB = 20;
export const ACCEPT = ".pdf,.png,.jpg,.jpeg,.doc,.docx,.xls,.xlsx,.csv";

function errorMessage(err: any, fallback = "Something went wrong."): string {
  return err?.response?.data?.detail || err?.response?.data?.title || err?.message || fallback;
}

export function formatSize(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function usePortalDocuments(client: PortalDocumentsConfig["client"], base: string) {
  const [documents, setDocuments] = useState<PortalDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    client
      .get(`${base}/documents`)
      .then((res) => setDocuments(res.data.data))
      .catch((err) => setError(errorMessage(err)));
  }, [client, base]);

  useEffect(reload, [reload]);
  return { documents, error, reload };
}

/** Request a slot, send the bytes to storage, then confirm. */
export async function uploadPortalDocument(
  client: PortalDocumentsConfig["client"],
  base: string,
  file: File,
  docType: string
): Promise<void> {
  const contentType = file.type || "application/octet-stream";
  const req = await client.post(`${base}/documents/upload-request`, {
    original_filename: file.name,
    content_type: contentType,
    doc_type: docType,
  });
  const put = await fetch(req.data.upload_url, { method: "PUT", body: file, headers: { "Content-Type": contentType } });
  if (!put.ok) throw new Error("The upload to storage failed. Please try again.");
  await client.post(`${base}/documents/${req.data.id}/confirm`);
}

export function PortalDocuments({ client, base, docTypes }: PortalDocumentsConfig) {
  const { documents, error: loadError, reload } = usePortalDocuments(client, base);
  const [docType, setDocType] = useState(docTypes[0]?.value ?? "other");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tooBig = !!file && file.size > MAX_UPLOAD_MB * 1024 * 1024;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || tooBig) return;
    setBusy(true);
    setError(null);
    try {
      await uploadPortalDocument(client, base, file, docType);
      setFile(null);
      (e.target as HTMLFormElement).reset();
      reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function download(id: string) {
    try {
      const res = await client.get(`${base}/documents/${id}/download`);
      window.open(res.data.download_url, "_blank", "noopener");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const labelFor = (v: string | null) => docTypes.find((t) => t.value === v)?.label ?? v ?? "—";

  return (
    <div>
      <Card style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Upload a document</h3>
        <form onSubmit={submit}>
          <Field label="Document type">
            <Select value={docType} onChange={(e) => setDocType(e.target.value)}>
              {docTypes.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="File" hint={`PDF, image, Word, Excel or CSV, up to ${MAX_UPLOAD_MB} MB.`}>
            <input
              type="file"
              aria-label="File"
              accept={ACCEPT}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </Field>
          {tooBig && <ErrorBanner title="File too large" detail={`Choose a file under ${MAX_UPLOAD_MB} MB.`} />}
          {error && <ErrorBanner title="Could not upload" detail={error} onDismiss={() => setError(null)} />}
          <Button type="submit" disabled={!file || tooBig || busy}>
            {busy ? "Uploading…" : "Upload"}
          </Button>
        </form>
      </Card>

      {loadError && <ErrorBanner title="Could not load documents" detail={loadError} />}
      <Card style={{ padding: 0 }}>
        {!documents ? (
          <div style={{ padding: 24, fontSize: 13 }}>Loading…</div>
        ) : documents.length === 0 ? (
          <EmptyState title="No documents yet" hint="Documents you upload appear here and are visible to your organisation." />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>File</Th>
                <Th>Type</Th>
                <Th>Size</Th>
                <Th>Uploaded</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d.id}>
                  <Td>{d.original_filename}</Td>
                  <Td>{labelFor(d.doc_type)}</Td>
                  <Td>{formatSize(d.size_bytes)}</Td>
                  <Td>{new Date(d.created_at).toLocaleDateString()}</Td>
                  <Td style={{ textAlign: "right" }}>
                    <button
                      onClick={() => download(d.id)}
                      style={{ background: "none", border: "none", color: "var(--sf-steel)", cursor: "pointer", fontSize: 12 }}
                    >
                      Download
                    </button>
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
