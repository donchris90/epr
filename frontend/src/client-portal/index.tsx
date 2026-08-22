import { Navigate, Route, Routes } from "react-router-dom";
import ClientPortalProtectedRoute from "./lib/ProtectedRoute";
import ClientPortalShell from "./ClientPortalShell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ProjectsPage from "./pages/ProjectsPage";
import ApprovalsCenterPage from "./pages/ApprovalsCenterPage";
import NotificationsPage from "./pages/NotificationsPage";
import ProfilePage from "./pages/ProfilePage";
import ProjectDetailLayout from "./pages/project/ProjectDetailLayout";
import OverviewTab from "./pages/project/OverviewTab";
import ProgressTab from "./pages/project/ProgressTab";
import ScheduleTab from "./pages/project/ScheduleTab";
import DocumentsTab from "./pages/project/DocumentsTab";
import DrawingsTab from "./pages/project/DrawingsTab";
import CertificatesTab from "./pages/project/CertificatesTab";
import VariationsTab from "./pages/project/VariationsTab";
import InvoicesTab from "./pages/project/InvoicesTab";
import IssuesTab from "./pages/project/IssuesTab";

/** The real client-facing portal (as opposed to
 * modules/clp/ClientPortalAdminPage.tsx, the internal staff tool for
 * administering it) -- mounted at a wholly separate top-level path
 * (/portal/*, see App.tsx) with its own auth, shell, and API client,
 * so nothing here can collide with or destroy the existing internal
 * app tree. See docs/CLIENT_PORTAL_GAPS.md for the full picture of
 * what's real here vs documented-but-not-yet-backed. */
export default function ClientPortalApp() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />

      <Route element={<ClientPortalProtectedRoute />}>
        <Route element={<ClientPortalShell />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="approvals" element={<ApprovalsCenterPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="profile" element={<ProfilePage />} />

          <Route path="projects/:projectId" element={<ProjectDetailLayout />}>
            <Route index element={<OverviewTab />} />
            <Route path="progress" element={<ProgressTab />} />
            <Route path="schedule" element={<ScheduleTab />} />
            <Route path="documents" element={<DocumentsTab />} />
            <Route path="drawings" element={<DrawingsTab />} />
            <Route path="certificates" element={<CertificatesTab />} />
            <Route path="variations" element={<VariationsTab />} />
            <Route path="invoices" element={<InvoicesTab />} />
            <Route path="issues" element={<IssuesTab />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="dashboard" replace />} />
    </Routes>
  );
}
