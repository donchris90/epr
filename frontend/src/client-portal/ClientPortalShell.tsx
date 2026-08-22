import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clientPortalClient } from "./api/client";
import { clearClientSession, getClientRefreshToken, getClientOrgName } from "./lib/auth";
import { ClientNotificationBell } from "./components/ClientNotificationBell";

// Deliberately a short, flat list -- "feel like a customer portal,
// not an internal ERP screen" means this is NOT AppShell's 30+ item,
// 9-section sidebar. A client cares about their projects, what needs
// their sign-off, and their own account; everything project-specific
// (documents, certificates, variations, invoices, issues) lives one
// level down, inside a project, not as its own top-level nav entry.
const NAV = [
  { to: "/portal/dashboard", label: "Dashboard", icon: "🏠" },
  { to: "/portal/projects", label: "Projects", icon: "🏗️" },
  { to: "/portal/approvals", label: "Approvals", icon: "✅" },
  { to: "/portal/notifications", label: "Notifications", icon: "🔔" },
  { to: "/portal/profile", label: "My Account", icon: "👤" },
];

export default function ClientPortalShell() {
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const orgName = getClientOrgName();

  async function handleSignOut() {
    const refreshToken = getClientRefreshToken();
    if (refreshToken) {
      try {
        await clientPortalClient.post("/clp/auth/logout", {}, { headers: { Authorization: `Bearer ${refreshToken}` } });
      } catch {
        // Best-effort revoke, same reasoning as AppShell's own sign-out.
      }
    }
    clearClientSession();
    navigate("/portal/login");
  }

  return (
    <div className={`sf-shell${drawerOpen ? " sf-sidebar-open" : ""}`} style={{ display: "flex", minHeight: "100vh" }}>
      <div className="sf-mobile-header">
        <button className="sf-hamburger" onClick={() => setDrawerOpen(true)} aria-label="Open menu">
          ☰
        </button>
        <span className="sf-mono" style={{ fontSize: 13, color: "var(--sf-amber)" }}>
          Client Portal
        </span>
        <ClientNotificationBell />
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
        <div style={{ padding: "20px 20px 16px", borderBottom: "1px solid var(--sf-navy-800)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span
                className="sf-mono"
                style={{ color: "var(--sf-amber)", fontSize: 13, border: "1px solid var(--sf-amber)", borderRadius: 2, padding: "1px 5px" }}
              >
                SF
              </span>
              <span style={{ fontFamily: "var(--sf-font-display)", fontWeight: 600, fontSize: 16, color: "#fff" }}>
                Client Portal
              </span>
            </div>
            <ClientNotificationBell />
          </div>
          {orgName && (
            <div className="sf-mono" style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 6 }}>
              {orgName}
            </div>
          )}
        </div>

        <nav style={{ flex: 1, padding: "16px 12px" }}>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setDrawerOpen(false)}
              style={({ isActive }) => ({
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                borderRadius: "var(--sf-radius)",
                fontSize: 14,
                fontWeight: 500,
                textDecoration: "none",
                color: isActive ? "#fff" : "var(--sf-navy-200)",
                background: isActive ? "var(--sf-navy-800)" : "transparent",
                borderLeft: isActive ? "3px solid var(--sf-amber)" : "3px solid transparent",
                marginBottom: 4,
              })}
            >
              <span aria-hidden>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div style={{ padding: 16, borderTop: "1px solid var(--sf-navy-800)" }}>
          <button
            onClick={handleSignOut}
            style={{ background: "none", border: "none", color: "var(--sf-navy-400)", fontSize: 12, cursor: "pointer", padding: 0 }}
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
