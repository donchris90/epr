import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import EmployeesPage from "./EmployeesPage";
import TimesheetsPage from "./TimesheetsPage";
import PayrollPage from "./PayrollPage";

const TABS = [
  { to: "employees", label: "Employees" },
  { to: "timesheets", label: "Timesheets & Leave" },
  { to: "payroll", label: "Payroll" },
];

export default function WFMModule() {
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
        <Route index element={<Navigate to="employees" replace />} />
        <Route path="employees" element={<EmployeesPage />} />
        <Route path="timesheets" element={<TimesheetsPage />} />
        <Route path="payroll" element={<PayrollPage />} />
      </Routes>
    </div>
  );
}
