import { Navigate, Route, Routes } from "react-router-dom";
import VendorPortalProtectedRoute from "./lib/ProtectedRoute";
import VendorPortalShell from "./VendorPortalShell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import PurchaseOrdersPage from "./pages/PurchaseOrdersPage";
import PurchaseOrderDetailPage from "./pages/PurchaseOrderDetailPage";
import InvoicesPage from "./pages/InvoicesPage";
import ProfilePage from "./pages/ProfilePage";

/** The real vendor-facing portal -- mounted at a wholly separate
 * top-level path (/vendor/*, see App.tsx) with its own auth, shell,
 * and API client, so nothing here can collide with or destroy the
 * existing internal app tree. Same real architecture as the
 * subcontractor portal (subcontractor-portal/index.tsx) and the
 * client portal, deliberately replicated rather than reinvented. See
 * docs/SUBCONTRACTOR_VENDOR_PORTAL_GAPS.md for what's real here vs
 * documented-but-not-yet-backed (no Documents page -- confirmed
 * uploading a real document requires a permission a vendor token
 * doesn't and shouldn't have). */
export default function VendorPortalApp() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />

      <Route element={<VendorPortalProtectedRoute />}>
        <Route element={<VendorPortalShell />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="purchase-orders" element={<PurchaseOrdersPage />} />
          <Route path="purchase-orders/:id" element={<PurchaseOrderDetailPage />} />
          <Route path="invoices" element={<InvoicesPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="dashboard" replace />} />
    </Routes>
  );
}
