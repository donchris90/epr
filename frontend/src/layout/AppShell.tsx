import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearTokens, getRefreshToken, getTenantLabel } from "../lib/auth";
import { apiClient } from "../api/client";
import { NotificationBell } from "../components/NotificationBell";
import { GlobalSearch } from "../components/GlobalSearch";
import { UserAvatar } from "../components/UserAvatar";

const NAV = [
  { section: "Projects", items: [{ to: "/projects", label: "All Projects" }] },
  { section: "Approvals & Documents", items: [{ to: "/approvals", label: "Approval Center" }, { to: "/workflows", label: "Workflows" }, { to: "/documents", label: "Document Library" }, { to: "/notifications", label: "Notifications" }] },
  { section: "Pipeline", items: [{ to: "/business-development", label: "Business Development" }] },
  {
    section: "Tender-to-Contract",
    items: [
      { to: "/tenders", label: "Tenders" },
      { to: "/contracts", label: "Contracts" },
    ],
  },
  {
    section: "Field Operations",
    items: [
      { to: "/planning", label: "Planning" },
      { to: "/execution", label: "Execution" },
      { to: "/quality", label: "Quality" },
      { to: "/hse", label: "Health, Safety & Environment" },
    ],
  },
  {
    section: "Supply Chain",
    items: [
      { to: "/procurement", label: "Procurement" },
      { to: "/inventory", label: "Inventory & Warehouse" },
      { to: "/equipment", label: "Equipment & Fleet" },
      { to: "/fuel", label: "Fuel Management" },
      { to: "/workforce", label: "Workforce" },
      { to: "/subcontractors", label: "Subcontractors" },
      { to: "/survey", label: "Survey & Engineering" },
      { to: "/plant-quarry", label: "Plant & Quarry" },
    ],
  },
  {
    section: "Finance",
    items: [
      { to: "/finance", label: "Financial Management" },
      { to: "/billing", label: "Client Billing" },
      { to: "/project-controls", label: "Project Controls" },
    ],
  },
  {
    section: "Asset Lifecycle",
    items: [{ to: "/assets", label: "Assets" }],
  },
  {
    section: "Executive & Portals",
    items: [
      { to: "/dashboard", label: "Executive Dashboard" },
      { to: "/client-portal", label: "Client Portal" },
      { to: "/vendor-portal", label: "Vendor Portal" },
      { to: "/mobile-sync", label: "Mobile Sync" },
      { to: "/ai-assistant", label: "AI Assistant" },
    ],
  },
  {
    section: "Account",
    items: [
      { to: "/settings/profile", label: "My Profile" },
      { to: "/settings/security", label: "Security" },
      { to: "/settings/users", label: "Users & Roles" },
      { to: "/settings/roles", label: "Manage Roles" },
      { to: "/account/subscription", label: "Billing & Subscription" },
    ],
  },
];

export default function AppShell() {
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className={`sf-shell${drawerOpen ? " sf-sidebar-open" : ""}`} style={{ display: "flex", minHeight: "100vh" }}>
      {/* Only rendered visually on narrow viewports (see tokens.css) --
          the desktop layout below never shows this at all. */}
      <div className="sf-mobile-header">
        <button className="sf-hamburger" onClick={() => setDrawerOpen(true)} aria-label="Open menu">
          ☰
        </button>
        <span className="sf-mono" style={{ fontSize: 13, color: "var(--sf-amber)" }}>
          SiteForge
        </span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <GlobalSearch variant="icon" />
          <NotificationBell />
        </div>
      </div>

      {drawerOpen && <div className="sf-sidebar-backdrop" onClick={() => setDrawerOpen(false)} />}

      <aside
        className="sf-sidebar"
        style={{
          width: "var(--sf-sidebar-w)",
          flexShrink: 0,
          background: "var(--sf-navy-950)",
          color: "var(--sf-navy-200)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "20px 20px 16px",
            borderBottom: "1px solid var(--sf-navy-800)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span
                className="sf-mono"
                style={{
                  color: "var(--sf-amber)",
                  fontSize: 13,
                  border: "1px solid var(--sf-amber)",
                  borderRadius: 2,
                  padding: "1px 5px",
                }}
              >
                SF
              </span>
              <span style={{ fontFamily: "var(--sf-font-display)", fontWeight: 600, fontSize: 16, color: "#fff" }}>
                SiteForge
              </span>
            </div>
            <NotificationBell />
          </div>
          <div className="sf-mono" style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 6 }}>
            {getTenantLabel()}
          </div>
          <UserAvatar />
          <div style={{ marginTop: 12 }}>
            <GlobalSearch variant="inline" />
          </div>
        </div>

        <nav style={{ flex: 1, padding: "16px 12px", overflowY: "auto" }}>
          {NAV.map((group) => (
            <div key={group.section} style={{ marginBottom: 20 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.03em",
                  textTransform: "uppercase",
                  color: "var(--sf-navy-400)",
                  padding: "0 8px",
                  marginBottom: 6,
                }}
              >
                {group.section}
              </div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setDrawerOpen(false)}
                  style={({ isActive }) => ({
                    display: "block",
                    padding: "9px 10px",
                    borderRadius: "var(--sf-radius)",
                    fontSize: 13,
                    fontWeight: 500,
                    textDecoration: "none",
                    color: isActive ? "#fff" : "var(--sf-navy-200)",
                    background: isActive ? "var(--sf-navy-800)" : "transparent",
                    borderLeft: isActive ? "3px solid var(--sf-amber)" : "3px solid transparent",
                    marginBottom: 2,
                  })}
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div style={{ padding: 16, borderTop: "1px solid var(--sf-navy-800)" }}>
          <button
            onClick={async () => {
              const refreshToken = getRefreshToken();
              if (refreshToken) {
                // Best-effort: revoke the refresh token server-side so
                // it can't be used again even if it leaked. Logout
                // should still proceed locally even if this call fails
                // (e.g. the token was already expired or the network
                // is briefly unavailable) -- the user's intent to sign
                // out shouldn't be blocked by a revocation call failing.
                try {
                  await apiClient.post(
                    "/auth/logout",
                    {},
                    { headers: { Authorization: `Bearer ${refreshToken}` } }
                  );
                } catch {
                  // Ignored deliberately -- see comment above.
                }
              }
              clearTokens();
              navigate("/login");
            }}
            style={{
              background: "none",
              border: "none",
              color: "var(--sf-navy-400)",
              fontSize: 12,
              cursor: "pointer",
              padding: 0,
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="sf-main" style={{ flex: 1, padding: "32px 40px", maxWidth: 1100 }}>
        <Outlet />
      </main>
    </div>
  );
}
