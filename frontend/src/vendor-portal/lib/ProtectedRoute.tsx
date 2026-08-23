import { Navigate, Outlet, useLocation } from "react-router-dom";
import { isPortalAuthenticated } from "./auth";

export default function VendorPortalProtectedRoute() {
  const location = useLocation();
  if (!isPortalAuthenticated()) {
    return <Navigate to="/vendor/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
