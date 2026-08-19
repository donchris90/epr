import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { apiClient } from "../../api/client";
import { PageHeader, Card, Badge, ErrorBanner, formatMoney } from "../../components/ui";

interface ProjectDetail {
  id: string;
  name: string;
  status: string;
  client_id: string | null;
  client_name: string | null;
  project_manager_id: string | null;
  start_date: string | null;
  end_date: string | null;
  contract_value: string | null;
  currency: string | null;
}

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Could not load this project.";
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 600 }}>{value}</div>
    </div>
  );
}

/** Real project overview -- deliberately just the Overview tab for
 * now, not the full multi-tab workspace (WBS/Schedule/BOQ/Budget/
 * Procurement/etc.) a complete project workspace would eventually
 * have -- that's real, separate, larger work across many modules,
 * not attempted here. Shows only fields the backend actually
 * computes: no budget/actual-cost/progress placeholders, since those
 * genuinely aren't aggregated yet (see
 * backend/app/projects/services.py:get_project_detail's own
 * docstring on why). */
export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get(`/projects/${projectId}`)
      .then((res) => setProject(res.data))
      .catch((err) => setError(getErrorMessage(err)));
  }, [projectId]);

  if (error) {
    return (
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 24px" }}>
        <ErrorBanner title="Could not load project" detail={error} />
        <Link to="/projects">← Back to all projects</Link>
      </div>
    );
  }

  if (!project) {
    return <div style={{ padding: 32, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>;
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 24px" }}>
      <Link to="/projects" style={{ fontSize: 12, color: "var(--sf-steel)" }}>
        ← All projects
      </Link>

      <PageHeader
        eyebrow="Project"
        title={project.name}
        action={<Badge tone={project.status === "active" ? "green" : "neutral"}>{project.status.replace(/_/g, " ")}</Badge>}
      />

      <Card>
        <div className="row g-3">
          <div className="col-6 col-lg-3">
            <Stat label="Client" value={project.client_name ?? "Not assigned"} />
          </div>
          <div className="col-6 col-lg-3">
            <Stat label="Contract value" value={project.contract_value ? formatMoney(project.contract_value, project.currency ?? "NGN") : "No contract linked yet"} />
          </div>
          <div className="col-6 col-lg-3">
            <Stat label="Start date" value={project.start_date ?? "—"} />
          </div>
          <div className="col-6 col-lg-3">
            <Stat label="End date" value={project.end_date ?? "—"} />
          </div>
        </div>
      </Card>

      <div style={{ marginTop: 16, padding: 16, background: "var(--sf-paper-dim)", borderRadius: "var(--sf-radius)", fontSize: 13, color: "var(--sf-navy-600)" }}>
        Budget, actual cost, and progress roll-ups aren't connected to this overview yet — those live in Estimating,
        Finance, and Execution respectively. This page shows what's genuinely tracked on the project record itself.
      </div>
    </div>
  );
}
