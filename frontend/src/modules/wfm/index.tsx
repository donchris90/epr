import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import WorkforceDashboardPage from "./WorkforceDashboardPage";
import EmployeesPage from "./EmployeesPage";
import EmployeeDetailPage from "./EmployeeDetailPage";
import TimesheetsPage from "./TimesheetsPage";
import PayrollPage from "./PayrollPage";
import PayrollRunDetailPage from "./PayrollRunDetailPage";

const TABS = [
  { to: "/workforce/dashboard", label: "Dashboard" },
  { to: "/workforce/employees", label: "Employees" },
  { to: "/workforce/timesheets", label: "Timesheets & Leave" },
  { to: "/workforce/payroll", label: "Payroll" },
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
        <Route index element={<Navigate to="/workforce/dashboard" replace />} />
        <Route path="dashboard" element={<WorkforceDashboardPage />} />
        <Route path="employees" element={<EmployeesPage />} />
        <Route path="employees/:employeeId" element={<EmployeeDetailPage />} />
        <Route path="timesheets" element={<TimesheetsPage />} />
        <Route path="payroll" element={<PayrollPage />} />
        <Route path="payroll/:runId" element={<PayrollRunDetailPage />} />
      </Routes>
    </div>
  );
}
