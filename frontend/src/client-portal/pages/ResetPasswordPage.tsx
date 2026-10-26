import { PortalResetPassword } from "../../components/PortalPasswordReset";
import { clientPortalClient } from "../api/client";

export default function ClientResetPasswordPage() {
  return <PortalResetPassword client={clientPortalClient} apiPrefix="/clp" basePath="/portal" portalName="Client Portal" />;
}
