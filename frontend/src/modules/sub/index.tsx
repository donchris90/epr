import { Route, Routes } from "react-router-dom";
import SubcontractorDashboardPage from "./SubcontractorDashboardPage";
import SubcontractorsPage from "./SubcontractorsPage";
import AgreementDetailPage from "./AgreementDetailPage";

export default function SUBModule() {
  return (
    <Routes>
      <Route index element={<SubcontractorDashboardPage />} />
      <Route path="list" element={<SubcontractorsPage />} />
      <Route path="agreements/:agreementId" element={<AgreementDetailPage />} />
    </Routes>
  );
}
