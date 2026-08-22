import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { PageHeader, Badge, formatMoney } from "../../../components/ui";
import { useClientProject } from "../../hooks";
import { QueryState } from "../../components/QueryState";

// One tab per project-scoped section (items 4-14 from the brief).
// "Drawings" and "Documents" are the same underlying Document data
// (see backend/app/modules/clp/services.py:get_client_documents),
// kept as two tabs anyway because a client thinks of them as
// different things even though the backend doesn't model them
// separately. "Issues" doubles as "Messages" -- see that tab's own
// note for why.
const TABS = [
  { to: "", label: "Overview", end: true },
  { to: "progress", label: "Progress" },
  { to: "schedule", label: "Schedule" },
  { to: "documents", label: "Documents" },
  { to: "drawings", label: "Drawings" },
  { to: "certificates", label: "Certificates" },
  { to: "variations", label: "Variations" },
  { to: "invoices", label: "Invoices & Payments" },
  { to: "issues", label: "Issues & Messages" },
];

function statusTone(status: string): "green" | "amber" | "neutral" {
  if (status === "active") return "green";
  if (status === "on_hold") return "amber";
  return "neutral";
}

export default function ProjectDetailLayout() {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useClientProject(projectId);

  return (
    <div>
      <Link to="/portal/projects" style={{ fontSize: 12, color: "var(--sf-steel)" }}>
        ← All projects
      </Link>

      <QueryState query={project} emptyTitle="Project not found">
        {(data: any) => (
          <>
            <PageHeader
              eyebrow="Project"
              title={data.name}
              action={<Badge tone={statusTone(data.status)}>{data.status.replace(/_/g, " ")}</Badge>}
            />
            <div style={{ display: "flex", gap: 24, fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 20, marginTop: -8 }}>
              <span>Start: {data.start_date ?? "—"}</span>
              <span>End: {data.end_date ?? "—"}</span>
              {data.contract_value && <span>Contract value: {formatMoney(data.contract_value, data.currency ?? "NGN")}</span>}
            </div>
          </>
        )}
      </QueryState>

      <div
        style={{
          display: "flex",
          gap: 4,
          borderBottom: "1px solid var(--sf-line)",
          marginBottom: 20,
          overflowX: "auto",
        }}
      >
        {TABS.map((tab) => (
          <NavLink
            key={tab.label}
            to={tab.to}
            end={tab.end}
            style={({ isActive }) => ({
              padding: "10px 14px",
              fontSize: 13,
              fontWeight: 600,
              whiteSpace: "nowrap",
              textDecoration: "none",
              color: isActive ? "var(--sf-navy-900)" : "var(--sf-navy-400)",
              borderBottom: isActive ? "2px solid var(--sf-amber)" : "2px solid transparent",
            })}
          >
            {tab.label}
          </NavLink>
        ))}
      </div>

      <Outlet />
    </div>
  );
}
