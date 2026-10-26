import { Link, useParams } from "react-router-dom";
import WorkflowBuilderPage from "./WorkflowBuilderPage";
import { useWorkflowDefinition } from "./hooks";
import { ErrorBanner } from "../../components/ui";

/** Loads a draft and opens the builder on it in edit mode. A definition
 * that is active, or that any approval has used, is not edited in place
 * (the backend refuses too); the person is pointed at "New version". */
export default function WorkflowEditPage() {
  const { id } = useParams<{ id: string }>();
  const { definition, loading, error } = useWorkflowDefinition(id);

  if (error) {
    return (
      <div style={{ maxWidth: 700, margin: "0 auto", padding: "32px 24px" }}>
        <ErrorBanner title="Could not load this workflow" detail={error} />
      </div>
    );
  }
  if (loading || !definition) {
    return <div style={{ maxWidth: 700, margin: "0 auto", padding: "32px 24px", fontSize: 13 }}>Loading…</div>;
  }
  if (!definition.editable) {
    return (
      <div style={{ maxWidth: 700, margin: "0 auto", padding: "32px 24px" }}>
        <ErrorBanner
          title="This workflow can't be edited in place"
          detail={
            definition.active
              ? "It is active. Deactivate it first, or create a new version."
              : "It has already been used by an approval, so changing it would rewrite history. Create a new version instead."
          }
        />
        <p style={{ marginTop: 12, fontSize: 13 }}>
          <Link to={`/workflows/new?module_name=${definition.module_name}&entity_type=${definition.entity_type}`}>
            Create a new version
          </Link>
          {" · "}
          <Link to={`/workflows/${definition.id}`}>Back</Link>
        </p>
      </div>
    );
  }
  return <WorkflowBuilderPage editing={definition} />;
}
