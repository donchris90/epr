import { PageHeader } from "../../components/ui";
import { PortalDocuments } from "../../components/PortalDocuments";
import { vendorPortalClient } from "../api/client";
import { getPortalUserId } from "../lib/auth";

export const VENDOR_DOC_TYPES = [
  { value: "trade_license", label: "Trade licence" },
  { value: "tax_clearance", label: "Tax clearance" },
  { value: "insurance", label: "Insurance" },
  { value: "certificate", label: "Certificate" },
  { value: "invoice", label: "Invoice" },
  { value: "other", label: "Other" },
];

export default function VendorDocumentsPage() {
  return (
    <div>
      <PageHeader eyebrow="Vendor Portal" title="Documents" />
      <PortalDocuments client={vendorPortalClient} base={`/vnp/vendor-users/${getPortalUserId()}`} docTypes={VENDOR_DOC_TYPES} />
    </div>
  );
}
