import { Navigate, Outlet } from "react-router-dom";
import { isPlatformAdminAuthenticated } from "./platformAdminAuth";

export default function PlatformAdminProtectedRoute() {
  if (!isPlatformAdminAuthenticated()) {
    return <Navigate to="/platform-admin/login" replace />;
  }
  return <Outlet />;
}
