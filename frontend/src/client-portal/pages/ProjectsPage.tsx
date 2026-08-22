import { Link } from "react-router-dom";
import { PageHeader, Card, Table, Th, Td, Badge } from "../../components/ui";
import { useClientProjects } from "../hooks";
import { QueryState } from "../components/QueryState";

interface ProjectSummary {
  id: string;
  name: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
}

function statusTone(status: string): "green" | "amber" | "neutral" {
  if (status === "active") return "green";
  if (status === "on_hold") return "amber";
  return "neutral";
}

/** Projects (item 2): every project assigned to this client account,
 * as a scannable table -- the Dashboard's cards are for a quick
 * glance, this is for finding a specific project by name/status. */
export default function ProjectsPage() {
  const projects = useClientProjects();

  return (
    <div>
      <PageHeader eyebrow="Your projects" title="Projects" />
      <Card style={{ padding: 0 }}>
        <QueryState
          query={projects}
          emptyTitle="No projects assigned yet"
          emptyHint="Your project manager will assign you to a project, and it will appear here."
        >
          {(data: ProjectSummary[]) => (
            <Table>
              <thead>
                <tr>
                  <Th>Project</Th>
                  <Th>Status</Th>
                  <Th>Start</Th>
                  <Th>End</Th>
                </tr>
              </thead>
              <tbody>
                {data.map((p) => (
                  <tr key={p.id}>
                    <Td>
                      <Link to={`/portal/projects/${p.id}`} style={{ color: "var(--sf-navy-900)", fontWeight: 600, textDecoration: "none" }}>
                        {p.name}
                      </Link>
                    </Td>
                    <Td>
                      <Badge tone={statusTone(p.status)}>{p.status.replace(/_/g, " ")}</Badge>
                    </Td>
                    <Td mono>{p.start_date ?? "—"}</Td>
                    <Td mono>{p.end_date ?? "—"}</Td>
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
