import { Navigate, Outlet, useLocation } from "react-router-dom";
import { isClientAuthenticated } from "./auth";

export default function ClientPortalProtectedRoute() {
  const location = useLocation();
  if (!isClientAuthenticated()) {
    return <Navigate to="/portal/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
