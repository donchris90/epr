import { PortalForgotPassword } from "../../components/PortalPasswordReset";
import { clientPortalClient } from "../api/client";

export default function ClientForgotPasswordPage() {
  return <PortalForgotPassword client={clientPortalClient} apiPrefix="/clp" basePath="/portal" portalName="Client Portal" />;
}
