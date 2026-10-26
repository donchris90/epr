import { PageHeader } from "../../components/ui";
import { PortalDocuments } from "../../components/PortalDocuments";
import { subcontractorPortalClient } from "../api/client";
import { getPortalUserId } from "../lib/auth";

export const SUBCONTRACTOR_DOC_TYPES = [
  { value: "insurance", label: "Insurance" },
  { value: "certificate", label: "Certificate" },
  { value: "method_statement", label: "Method statement" },
  { value: "drawing", label: "Drawing" },
  { value: "invoice", label: "Invoice" },
  { value: "other", label: "Other" },
];

export default function SubcontractorDocumentsPage() {
  return (
    <div>
      <PageHeader eyebrow="Subcontractor Portal" title="Documents" />
      <PortalDocuments
        client={subcontractorPortalClient}
        base={`/scp/portal-users/${getPortalUserId()}`}
        docTypes={SUBCONTRACTOR_DOC_TYPES}
      />
    </div>
  );
}
