import { Navigate, Outlet, useLocation } from "react-router-dom";
import { isPortalAuthenticated } from "./auth";

export default function SubcontractorPortalProtectedRoute() {
  const location = useLocation();
  if (!isPortalAuthenticated()) {
    return <Navigate to="/subcontractor/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
