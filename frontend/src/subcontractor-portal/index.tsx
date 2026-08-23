import { Navigate, Route, Routes } from "react-router-dom";
import SubcontractorPortalProtectedRoute from "./lib/ProtectedRoute";
import SubcontractorPortalShell from "./SubcontractorPortalShell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import AgreementsPage from "./pages/AgreementsPage";
import AgreementDetailPage from "./pages/AgreementDetailPage";
import ClaimsPage from "./pages/ClaimsPage";
import ProfilePage from "./pages/ProfilePage";

/** The real subcontractor-facing portal -- mounted at a wholly
 * separate top-level path (/subcontractor/*, see App.tsx) with its
 * own auth, shell, and API client, so nothing here can collide with
 * or destroy the existing internal app tree. See
 * docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md for the full picture of
 * what's real here vs documented-but-not-yet-backed (there is
 * genuinely no "projects" concept for a subcontractor -- the real
 * unit is an Agreement, see that document for the full reasoning). */
export default function SubcontractorPortalApp() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />

      <Route element={<SubcontractorPortalProtectedRoute />}>
        <Route element={<SubcontractorPortalShell />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="agreements" element={<AgreementsPage />} />
          <Route path="agreements/:id" element={<AgreementDetailPage />} />
          <Route path="claims" element={<ClaimsPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="dashboard" replace />} />
    </Routes>
  );
}
