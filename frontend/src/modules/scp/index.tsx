import { useEffect } from "react";
import { Navigate, NavLink, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { PageHeader, Select, Badge, Button } from "../../components/ui";
import { useScpStore } from "./store";
import { useMyAgreements } from "./hooks";
import AccessPage from "./AccessPage";
import DashboardPage from "./DashboardPage";
import AgreementsPage from "./AgreementsPage";
import AgreementDetailPage from "./AgreementDetailPage";
import ProgressPage from "./ProgressPage";
import ClaimsPage from "./ClaimsPage";
import CertificatesPage from "./CertificatesPage";

const BASE = "/subcontractor-portal";

const TABS = [
  { to: BASE, label: "Overview", end: true },
  { to: `${BASE}/agreements`, label: "Agreements" },
  { to: `${BASE}/progress`, label: "Progress" },
  { to: `${BASE}/certificates`, label: "Payment certificates" },
  { to: `${BASE}/claims`, label: "Claims" },
  { to: `${BASE}/access`, label: "Profile & access" },
];

function PortalLayout() {
  const session = useScpStore((s) => s.session);
  const agreementId = useScpStore((s) => s.agreementId);
  const setAgreementId = useScpStore((s) => s.setAgreementId);
  const clearSession = useScpStore((s) => s.clearSession);
  const { data: agreements } = useMyAgreements();
  const location = useLocation();

  // Default the focused agreement to the first active one (or the first at all).
  useEffect(() => {
    if (!agreements?.length) return;
    if (agreementId && agreements.some((a) => a.id === agreementId)) return;
    setAgreementId((agreements.find((a) => a.status === "active") ?? agreements[0]).id);
  }, [agreements, agreementId, setAgreementId]);

  if (!session && !location.pathname.endsWith("/access")) {
    return <Navigate to={`${BASE}/access`} replace />;
  }

  return (
    <div>
      <PageHeader
        eyebrow="Subcontractor Portal"
        title="Subcontractor workspace"
        action={
          session && (
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Badge tone="steel">{session.email ?? session.id.slice(0, 8)}</Badge>
              <Button variant="secondary" onClick={clearSession}>
                Switch user
              </Button>
            </div>
          )
        }
      />

      {session && (
        <>
          <nav style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 16, borderBottom: "1px solid var(--sf-line)" }}>
            {TABS.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.end}
                style={({ isActive }) => ({
                  padding: "8px 14px",
                  fontSize: 13,
                  fontWeight: 600,
                  textDecoration: "none",
                  color: isActive ? "var(--sf-navy-900)" : "var(--sf-navy-400)",
                  borderBottom: isActive ? "2px solid var(--sf-amber)" : "2px solid transparent",
                  marginBottom: -1,
                })}
              >
                {t.label}
              </NavLink>
            ))}
          </nav>

          {!!agreements?.length && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20, maxWidth: 460 }}>
              <span className="sf-mono" style={{ fontSize: 11, textTransform: "uppercase", color: "var(--sf-navy-400)", whiteSpace: "nowrap" }}>
                Agreement
              </span>
              <Select value={agreementId ?? ""} onChange={(e) => setAgreementId(e.target.value)} aria-label="Active agreement">
                {agreements.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.agreement_number} ({a.status})
                  </option>
                ))}
              </Select>
            </div>
          )}
        </>
      )}

      <Outlet />
    </div>
  );
}

export default function SCPModule() {
  return (
    <Routes>
      <Route element={<PortalLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="agreements" element={<AgreementsPage />} />
        <Route path="agreements/:agreementId" element={<AgreementDetailPage />} />
        <Route path="progress" element={<ProgressPage />} />
        <Route path="certificates" element={<CertificatesPage />} />
        <Route path="claims" element={<ClaimsPage />} />
        <Route path="access" element={<AccessPage />} />
        <Route path="*" element={<Navigate to={BASE} replace />} />
      </Route>
    </Routes>
  );
}
