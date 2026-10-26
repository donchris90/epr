import { useEffect, useState } from "react";
import { apiClient, getErrorMessage } from "../api/client";
import { Card, Button, Table, Th, Td, Badge, EmptyState, ErrorBanner } from "./ui";

interface Row {
  id: string;
  doc_type: string | null;
  original_filename: string | null;
  size_bytes: number | null;
  status: string;
  created_at: string;
}

function size(bytes: number | null) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Staff view of the documents one vendor or subcontractor organisation
 * has uploaded through its portal (read-only; staff manage them in the
 * Document Library). Backed by GET /v1/documents?source=...&portal_owner_id=...
 * which needs documents:read. */
export default function PortalOrgDocuments({
  source,
  ownerId,
  name,
  onClose,
}: {
  source: "vendor" | "subcontractor";
  ownerId: string;
  name: string;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setRows(null);
    setError(null);
    apiClient
      .get("/documents", { params: { source, portal_owner_id: ownerId } })
      .then((res) => live && setRows(res.data.data))
      .catch((err) => {
        if (!live) return;
        setError(getErrorMessage(err));
        setRows([]);
      });
    return () => {
      live = false;
    };
  }, [source, ownerId]);

  async function download(row: Row) {
    setError(null);
    try {
      const res = await apiClient.get(`/documents/${row.id}`);
      if (res.data.download_url) window.open(res.data.download_url, "_blank", "noopener");
      else setError("This document has no download link yet — it may still be uploading.");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <Card style={{ marginBottom: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ fontSize: 14 }}>Documents uploaded by {name}</h3>
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </div>
      {error && <ErrorBanner title="Documents" detail={error} onDismiss={() => setError(null)} />}
      {rows === null ? (
        <p style={{ fontSize: 13 }}>Loading…</p>
      ) : rows.length === 0 ? (
        <EmptyState compact title="Nothing uploaded through the portal yet." />
      ) : (
        <Table ariaLabel={`Documents from ${name}`}>
          <thead>
            <tr>
              <Th>File</Th>
              <Th>Type</Th>
              <Th>Size</Th>
              <Th>Uploaded</Th>
              <Th>Status</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <Td>{r.original_filename ?? "—"}</Td>
                <Td>{r.doc_type ?? "—"}</Td>
                <Td mono>{size(r.size_bytes)}</Td>
                <Td>{new Date(r.created_at).toLocaleDateString()}</Td>
                <Td>{r.status === "uploaded" ? <Badge tone="green">Ready</Badge> : <Badge tone="amber">{r.status}</Badge>}</Td>
                <Td>
                  {r.status === "uploaded" && (
                    <button
                      onClick={() => download(r)}
                      aria-label={`Download ${r.original_filename ?? "document"}`}
                      style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                    >
                      Download
                    </button>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}
