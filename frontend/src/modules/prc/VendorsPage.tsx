import { useState } from "react";
import { PageHeader, Card, Button, Table, Th, Td, Badge, EmptyState, Input, Field, ErrorBanner } from "../../components/ui";
import { getErrorMessage } from "../../api/client";
import { useUploadDocument } from "../../api/documents";
import { useVendors, useCreateVendor, useAddComplianceDocument } from "./hooks";

export default function VendorsPage() {
  const { data: vendors, isLoading } = useVendors();
  const createVendor = useCreateVendor();

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [taxRef, setTaxRef] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [docVendorId, setDocVendorId] = useState<string | null>(null);
  const [docType, setDocType] = useState("");
  const [docValidUntil, setDocValidUntil] = useState("");
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const uploadDocument = useUploadDocument();
  const addComplianceDoc = useAddComplianceDocument(docVendorId || undefined);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createVendor.mutateAsync({ name, tax_registration_number: taxRef || undefined });
      setName("");
      setTaxRef("");
      setShowForm(false);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function handleAddDoc(e: React.FormEvent) {
    e.preventDefault();
    if (!docVendorId) return;
    setDocError(null);
    try {
      let documentId: string | undefined;
      if (docFile) {
        const uploaded = await uploadDocument.mutateAsync({ file: docFile, docType });
        documentId = uploaded.id;
      }
      await addComplianceDoc.mutateAsync({ doc_type: docType, valid_until: docValidUntil || undefined, document_id: documentId });
      setDocType("");
      setDocValidUntil("");
      setDocFile(null);
      setDocVendorId(null);
    } catch (err) {
      setDocError(getErrorMessage(err));
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Procurement"
        title="Vendors"
        action={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New vendor"}</Button>}
      />

      {error && <ErrorBanner title="Couldn't add vendor" detail={error} onDismiss={() => setError(null)} />}

      {showForm && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={handleCreate}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <Field label="Vendor name">
                <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="ABC Building Materials Ltd" />
              </Field>
              <Field label="Tax registration number (optional)">
                <Input value={taxRef} onChange={(e) => setTaxRef(e.target.value)} />
              </Field>
            </div>
            <Button type="submit" disabled={createVendor.isPending}>
              {createVendor.isPending ? "Saving…" : "Save vendor"}
            </Button>
          </form>
        </Card>
      )}

      {docVendorId && (
        <Card style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, marginBottom: 12 }}>Add compliance document</h3>
          {docError && <ErrorBanner title="Couldn't save document" detail={docError} onDismiss={() => setDocError(null)} />}
          <form onSubmit={handleAddDoc}>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12, marginBottom: 12 }}>
              <Field label="Document type">
                <Input required placeholder="e.g. Tax clearance, Insurance" value={docType} onChange={(e) => setDocType(e.target.value)} />
              </Field>
              <Field label="Valid until">
                <Input type="date" value={docValidUntil} onChange={(e) => setDocValidUntil(e.target.value)} />
              </Field>
            </div>
            <Field label="File (optional)">
              <input
                type="file"
                onChange={(e) => setDocFile(e.target.files?.[0] ?? null)}
                style={{ fontSize: 13 }}
              />
            </Field>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <Button type="submit" disabled={addComplianceDoc.isPending || uploadDocument.isPending}>
                {uploadDocument.isPending ? "Uploading…" : addComplianceDoc.isPending ? "Saving…" : "Add"}
              </Button>
              <Button type="button" variant="secondary" onClick={() => setDocVendorId(null)}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      {isLoading ? (
        <p>Loading…</p>
      ) : !vendors?.length ? (
        <EmptyState title="No vendors registered" hint="Register a vendor to start requesting quotes and issuing purchase orders." />
      ) : (
        <Card style={{ padding: 0 }}>
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Tax reference</Th>
                <Th>Status</Th>
                <Th></Th>
              </tr>
            </thead>
            <tbody>
              {vendors.map((v: any) => (
                <tr key={v.id}>
                  <Td>{v.name}</Td>
                  <Td mono>{v.tax_registration_number || "—"}</Td>
                  <Td>
                    <Badge tone={v.status === "active" ? "green" : "neutral"}>{v.status}</Badge>
                  </Td>
                  <Td>
                    <button
                      onClick={() => setDocVendorId(v.id)}
                      style={{ background: "none", border: "none", color: "var(--sf-steel)", fontSize: 12, fontWeight: 600, cursor: "pointer" }}
                    >
                      Add compliance doc
                    </button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
