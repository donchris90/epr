import { Route, Routes } from "react-router-dom";
import EquipmentPage from "./EquipmentPage";
import EquipmentDetailPage from "./EquipmentDetailPage";

export default function EQPModule() {
  return (
    <Routes>
      <Route index element={<EquipmentPage />} />
      <Route path=":equipmentId" element={<EquipmentDetailPage />} />
    </Routes>
  );
}
