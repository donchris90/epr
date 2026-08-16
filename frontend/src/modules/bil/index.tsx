import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import CertificatesPage from "./CertificatesPage";
import CertificateDetailPage from "./CertificateDetailPage";
import VariationOrdersPage from "./VariationOrdersPage";
import OutstandingInvoicesPage from "./OutstandingInvoicesPage";

const TABS = [
  { to: "/billing/certificates", label: "Certificates" },
  { to: "/billing/variation-orders", label: "Variation Orders" },
  { to: "/billing/outstanding", label: "Outstanding Invoices" },
];

export default function BILModule() {
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
        <Route index element={<Navigate to="/billing/certificates" replace />} />
        <Route path="certificates" element={<CertificatesPage />} />
        <Route path="certificates/:certificateId" element={<CertificateDetailPage />} />
        <Route path="variation-orders" element={<VariationOrdersPage />} />
        <Route path="outstanding" element={<OutstandingInvoicesPage />} />
      </Routes>
    </div>
  );
}
