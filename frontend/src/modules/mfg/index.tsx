import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import ProductionOrdersPage from "./ProductionOrdersPage";
import BomsPage from "./BomsPage";
import WorkCentersPage from "./WorkCentersPage";

const TABS = [
  { to: "/manufacturing/orders", label: "Production orders" },
  { to: "/manufacturing/boms", label: "Bills of materials" },
  { to: "/manufacturing/work-centers", label: "Work centers" },
];

export default function MFGModule() {
  return (
    <div>
      <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            style={({ isActive }) => ({
              padding: "6px 12px",
              fontSize: 12,
              fontWeight: 600,
              textDecoration: "none",
              color: isActive ? "var(--sf-navy-900)" : "var(--sf-navy-400)",
              borderBottom: isActive ? "2px solid var(--sf-amber)" : "2px solid transparent",
            })}
          >
            {tab.label}
          </NavLink>
        ))}
      </div>
      <Routes>
        <Route index element={<Navigate to="/manufacturing/orders" replace />} />
        <Route path="orders" element={<ProductionOrdersPage />} />
        <Route path="boms" element={<BomsPage />} />
        <Route path="work-centers" element={<WorkCentersPage />} />
      </Routes>
    </div>
  );
}
