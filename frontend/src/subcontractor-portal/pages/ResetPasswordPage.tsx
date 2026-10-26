import { PortalResetPassword } from "../../components/PortalPasswordReset";
import { subcontractorPortalClient } from "../api/client";

export default function SubcontractorResetPasswordPage() {
  return <PortalResetPassword client={subcontractorPortalClient} apiPrefix="/scp" basePath="/subcontractor" portalName="Subcontractor Portal" />;
}
