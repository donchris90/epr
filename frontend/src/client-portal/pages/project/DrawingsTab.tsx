import DocumentListTab from "./DocumentListTab";

/** Drawings (item 7, "where supported"): the same Document data as
 * the Documents tab, filtered to doc_type="drawing". There is no
 * dedicated drawing-register/versioning entity anywhere in this
 * codebase (sheet numbers, revision clouds, superseded-by links) --
 * this shows whatever was uploaded with that doc_type, nothing more.
 * See docs/CLIENT_PORTAL_GAPS.md. */
export default function DrawingsTab() {
  return (
    <DocumentListTab
      docType="drawing"
      emptyHint="Drawings uploaded with doc_type 'drawing' will appear here. If your team uploads drawings under a different type, ask them to use 'drawing' so this tab picks them up."
    />
  );
}
