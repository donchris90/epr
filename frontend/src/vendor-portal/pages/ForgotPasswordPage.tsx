import { PortalForgotPassword } from "../../components/PortalPasswordReset";
import { vendorPortalClient } from "../api/client";

export default function VendorForgotPasswordPage() {
  return <PortalForgotPassword client={vendorPortalClient} apiPrefix="/vnp" basePath="/vendor" portalName="Vendor Portal" />;
}
