import { Link } from "react-router-dom";
import { PageHeader, Card, Badge } from "../../components/ui";
import { useClientMe, useClientProjects, useClientProgress } from "../hooks";
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

function ProjectProgressBar({ projectId }: { projectId: string }) {
  const progress = useClientProgress(projectId);
  const pct = progress.data?.overall_percent_complete;
  if (progress.isLoading || pct == null) {
    return <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>Progress not yet available</div>;
  }
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--sf-navy-400)", marginBottom: 4 }}>
        <span>Overall progress</span>
        <span>{pct}%</span>
      </div>
      <div style={{ height: 6, borderRadius: 999, background: "var(--sf-paper-dim)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${Math.min(100, Math.max(0, pct))}%`, background: "var(--sf-amber)" }} />
      </div>
    </div>
  );
}

function ProjectCard({ project }: { project: ProjectSummary }) {
  return (
    <Link to={`/portal/projects/${project.id}`} style={{ textDecoration: "none", color: "inherit" }}>
      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "var(--sf-navy-900)" }}>{project.name}</div>
          <Badge tone={statusTone(project.status)}>{project.status.replace(/_/g, " ")}</Badge>
        </div>
        <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 12 }}>
          {project.start_date ?? "Start TBD"} — {project.end_date ?? "End TBD"}
        </div>
        <ProjectProgressBar projectId={project.id} />
      </Card>
    </Link>
  );
}

/** Dashboard (item 1): a summary of every project this client is
 * assigned to, each with a live progress rollup. Deliberately no
 * cross-project financial totals here (e.g. "total outstanding") --
 * there's no single backend aggregation for that across projects yet
 * (see docs/CLIENT_PORTAL_GAPS.md); each project's own Invoices tab
 * has the real, per-project numbers. */
export default function DashboardPage() {
  const me = useClientMe();
  const projects = useClientProjects();

  return (
    <div>
      <PageHeader
        eyebrow="Welcome"
        title={me.data?.client_organization_name ? `${me.data.client_organization_name}` : "Your Dashboard"}
      />
      <QueryState
        query={projects}
        emptyTitle="No projects assigned yet"
        emptyHint="Your project manager will assign you to a project, and it will appear here."
      >
        {(data: ProjectSummary[]) => (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
            {data.map((p) => (
              <ProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </QueryState>
    </div>
  );
}
