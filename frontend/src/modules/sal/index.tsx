import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import SalesOrdersPage from "./SalesOrdersPage";
import SalesInvoicesPage from "./SalesInvoicesPage";
import SalesSettingsPage from "./SalesSettingsPage";
import SalesDocumentPage from "./SalesDocumentPage";

const TABS = [
  { to: "/sales/orders", label: "Sales orders" },
  { to: "/sales/invoices", label: "Invoices" },
  { to: "/sales/settings", label: "Accounting settings" },
];

export default function SALModule() {
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
        <Route index element={<Navigate to="/sales/orders" replace />} />
        <Route path="orders" element={<SalesOrdersPage />} />
        <Route path="invoices" element={<SalesInvoicesPage />} />
        <Route path="settings" element={<SalesSettingsPage />} />
        <Route path="print/:orderId/invoice/:docId" element={<SalesDocumentPage kind="invoice" />} />
        <Route path="print/:orderId/delivery/:docId" element={<SalesDocumentPage kind="delivery" />} />
      </Routes>
    </div>
  );
}
