import { PortalResetPassword } from "../../components/PortalPasswordReset";
import { vendorPortalClient } from "../api/client";

export default function VendorResetPasswordPage() {
  return <PortalResetPassword client={vendorPortalClient} apiPrefix="/vnp" basePath="/vendor" portalName="Vendor Portal" />;
}
