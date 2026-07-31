import { Route, Routes } from "react-router-dom";
import TendersPage from "./TendersPage";
import TenderDetailPage from "./TenderDetailPage";
import EstimatePage from "../est/EstimatePage";

export default function TBMModule() {
  return (
    <Routes>
      <Route index element={<TendersPage />} />
      <Route path=":tenderId" element={<TenderDetailPage />} />
      <Route path=":tenderId/estimate" element={<EstimatePage />} />
    </Routes>
  );
}
