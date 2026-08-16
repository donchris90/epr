import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import DiariesPage from "./DiariesPage";
import DiaryDetailPage from "./DiaryDetailPage";
import ProgressPage from "./ProgressPage";
import SiteIssuesPage from "./SiteIssuesPage";

const TABS = [
  { to: "diaries", label: "Site Diaries" },
  { to: "progress", label: "Progress" },
  { to: "issues", label: "Site Issues" },
];

export default function EXEModule() {
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
        <Route index element={<Navigate to="diaries" replace />} />
        <Route path="diaries" element={<DiariesPage />} />
        <Route path="diaries/:diaryId" element={<DiaryDetailPage />} />
        <Route path="progress" element={<ProgressPage />} />
        <Route path="issues" element={<SiteIssuesPage />} />
      </Routes>
    </div>
  );
}
