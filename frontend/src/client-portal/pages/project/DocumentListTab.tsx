import { useParams } from "react-router-dom";
import { Table, Th, Td, Badge, Button } from "../../../components/ui";
import { useClientDocuments, useClientDocumentDownload } from "../../hooks";
import { QueryState } from "../../components/QueryState";

interface DocumentRow {
  id: string;
  original_filename: string;
  doc_type: string;
  status: string;
  created_at: string;
}

function DownloadButton({ projectId, documentId }: { projectId: string; documentId: string }) {
  const download = useClientDocumentDownload();

  async function handleClick() {
    const url = await download.mutateAsync({ projectId, documentId });
    window.open(url, "_blank", "noopener,noreferrer");
  }

  return (
    <Button variant="ghost" onClick={handleClick} disabled={download.isPending}>
      {download.isPending ? "Preparing…" : "Download"}
    </Button>
  );
}

/** Shared list used for both Documents (item 6) and Drawings (item 7)
 * -- docType narrows to the drawing subset when provided. There is no
 * separate drawing-register entity in this codebase (versioning,
 * revision clouds, sheet numbers); this is the same Document row,
 * filtered by doc_type. See docs/CLIENT_PORTAL_GAPS.md. */
export default function DocumentListTab({ docType, emptyHint }: { docType?: string; emptyHint: string }) {
  const { projectId } = useParams<{ projectId: string }>();
  const documents = useClientDocuments(projectId, docType);

  return (
    <QueryState query={documents} emptyTitle="No documents yet" emptyHint={emptyHint}>
      {(data: DocumentRow[]) => (
        <Table>
          <thead>
            <tr>
              <Th>File</Th>
              <Th>Type</Th>
              <Th>Uploaded</Th>
              <Th></Th>
            </tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.id}>
                <Td>{d.original_filename}</Td>
                <Td>
                  <Badge tone="steel">{d.doc_type.replace(/_/g, " ")}</Badge>
                </Td>
                <Td mono>{new Date(d.created_at).toLocaleDateString()}</Td>
                <Td>
                  <DownloadButton projectId={projectId!} documentId={d.id} />
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </QueryState>
  );
}
