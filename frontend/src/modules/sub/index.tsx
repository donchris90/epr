import { Route, Routes } from "react-router-dom";
import SubcontractorsPage from "./SubcontractorsPage";
import AgreementDetailPage from "./AgreementDetailPage";

export default function SUBModule() {
  return (
    <Routes>
      <Route index element={<SubcontractorsPage />} />
      <Route path="agreements/:agreementId" element={<AgreementDetailPage />} />
    </Routes>
  );
}
