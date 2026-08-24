import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import WarehousesPage from "./WarehousesPage";
import StockMovementsPage from "./StockMovementsPage";
import TransfersAndReservationsPage from "./TransfersAndReservationsPage";
import WasteAndReturnsPage from "./WasteAndReturnsPage";
import StockCountsPage from "./StockCountsPage";

const TABS = [
  { to: "/inventory/warehouses", label: "Warehouses" },
  { to: "/inventory/movements", label: "Stock Movements" },
  { to: "/inventory/transfers", label: "Transfers & Reservations" },
  { to: "/inventory/waste-returns", label: "Waste & Returns" },
  { to: "/inventory/stock-counts", label: "Stock Counts" },
];

export default function INVModule() {
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
        <Route index element={<Navigate to="/inventory/warehouses" replace />} />
        <Route path="warehouses" element={<WarehousesPage />} />
        <Route path="movements" element={<StockMovementsPage />} />
        <Route path="transfers" element={<TransfersAndReservationsPage />} />
        <Route path="waste-returns" element={<WasteAndReturnsPage />} />
        <Route path="stock-counts" element={<StockCountsPage />} />
      </Routes>
    </div>
  );
}
