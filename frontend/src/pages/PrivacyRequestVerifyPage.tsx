import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { apiClient } from "../api/client";
import { LegalLayout } from "./legal/LegalLayout";

/** Landing page for the confirmation link emailed after a public data
 * request. Posts the token once on load. */
export default function PrivacyRequestVerifyPage() {
  const { tenantId } = useParams();
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"working" | "ok" | "bad">(token ? "working" : "bad");

  useEffect(() => {
    if (!token) return;
    apiClient
      .post(`/public/privacy/${tenantId}/verify`, { token })
      .then(() => setState("ok"))
      .catch(() => setState("bad"));
  }, [tenantId, token]);

  return (
    <LegalLayout title="Confirm your request">
      {state === "working" && <p>Confirming…</p>}
      {state === "ok" && <p role="status">Thank you — your email is confirmed and your request is now with the team. You'll hear back by email.</p>}
      {state === "bad" && <p role="alert">This confirmation link is invalid or has expired. Please submit your request again.</p>}
    </LegalLayout>
  );
}
