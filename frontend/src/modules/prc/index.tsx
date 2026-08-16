import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import VendorsPage from "./VendorsPage";
import PurchaseRequestsPage from "./PurchaseRequestsPage";
import PurchaseOrdersPage from "./PurchaseOrdersPage";
import PurchaseOrderDetailPage from "./PurchaseOrderDetailPage";

const TABS = [
  { to: "/procurement/vendors", label: "Vendors" },
  { to: "/procurement/requests", label: "Purchase Requests" },
  { to: "/procurement/orders", label: "Purchase Orders" },
];

export default function PRCModule() {
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
        <Route index element={<Navigate to="/procurement/vendors" replace />} />
        <Route path="vendors" element={<VendorsPage />} />
        <Route path="requests" element={<PurchaseRequestsPage />} />
        <Route path="orders" element={<PurchaseOrdersPage />} />
        <Route path="orders/:poId" element={<PurchaseOrderDetailPage />} />
      </Routes>
    </div>
  );
}
