import { Link } from "react-router-dom";
import { PageHeader, Card, Badge, Table, Th, Td } from "../../components/ui";
import { useClientApprovalActions, useClientProjects } from "../hooks";
import { QueryState } from "../components/QueryState";

interface ApprovalAction {
  id: string;
  action_type: "progress_certificate" | "variation_order";
  target_id: string;
  decision: "approved" | "rejected";
  decided_at: string;
}

/** Approvals (item 10): a cross-project history of every decision
 * this client account has made (services list_approval_actions /
 * ClientApprovalAction, CLP-03 & CLP-05's own audit trail). Deciding
 * itself happens inline on each project's Certificates/Variations tab
 * -- this page is the record of what's already been decided, plus a
 * pointer to where pending items live per project. */
export default function ApprovalsCenterPage() {
  const actions = useClientApprovalActions();
  const projects = useClientProjects();

  return (
    <div>
      <PageHeader eyebrow="Your decisions" title="Approvals" />

      <Card style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 13, color: "var(--sf-navy-600)" }}>
          Certificates and variation orders waiting on your sign-off appear on each project's own Certificates and
          Variations tabs.
          {!projects.isLoading && (projects.data ?? []).length > 0 && (
            <>
              {" "}
              Jump to a project:{" "}
              {(projects.data ?? []).map((p: any, i: number) => (
                <span key={p.id}>
                  <Link to={`/portal/projects/${p.id}/certificates`} style={{ color: "var(--sf-steel)" }}>
                    {p.name}
                  </Link>
                  {i < projects.data.length - 1 ? ", " : ""}
                </span>
              ))}
            </>
          )}
        </div>
      </Card>

      <h3 style={{ fontSize: 14, marginBottom: 10 }}>Decision history</h3>
      <Card style={{ padding: 0 }}>
        <QueryState query={actions} emptyTitle="No decisions recorded yet" emptyHint="Every certificate or variation order you approve or reject will be listed here.">
          {(data: ApprovalAction[]) => (
            <Table>
              <thead>
                <tr>
                  <Th>Type</Th>
                  <Th>Decision</Th>
                  <Th>Date</Th>
                </tr>
              </thead>
              <tbody>
                {data.map((a) => (
                  <tr key={a.id}>
                    <Td>{a.action_type === "progress_certificate" ? "Progress certificate" : "Variation order"}</Td>
                    <Td>
                      <Badge tone={a.decision === "approved" ? "green" : "brick"}>{a.decision}</Badge>
                    </Td>
                    <Td mono>{new Date(a.decided_at).toLocaleString()}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </QueryState>
      </Card>
    </div>
  );
}
