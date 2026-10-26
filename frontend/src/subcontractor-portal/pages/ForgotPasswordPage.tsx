import { PortalForgotPassword } from "../../components/PortalPasswordReset";
import { subcontractorPortalClient } from "../api/client";

export default function SubcontractorForgotPasswordPage() {
  return <PortalForgotPassword client={subcontractorPortalClient} apiPrefix="/scp" basePath="/subcontractor" portalName="Subcontractor Portal" />;
}
