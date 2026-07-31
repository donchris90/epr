import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import AppShell from "./layout/AppShell";
import ProtectedRoute from "./lib/ProtectedRoute";
import BDCModule from "./modules/bdc";
import TBMModule from "./modules/tbm";
import ContractsPage from "./modules/ctm/ContractsPage";
import ContractDetailPage from "./modules/ctm/ContractDetailPage";
import PLNModule from "./modules/pln";
import EXEModule from "./modules/exe";
import PRCModule from "./modules/prc";
import FINModule from "./modules/fin";
import BILModule from "./modules/bil";
import INVModule from "./modules/inv";
import EQPModule from "./modules/eqp";
import FUELModule from "./modules/fuel";
import WFMModule from "./modules/wfm";
import SUBModule from "./modules/sub";
import QMSModule from "./modules/qms";
import HSEModule from "./modules/hse";
import SVYModule from "./modules/svy";
import PQModule from "./modules/pq";
import PCModule from "./modules/pc";
import ASTModule from "./modules/ast";
import EXDModule from "./modules/exd";
import CLPModule from "./modules/clp";
import VNPModule from "./modules/vnp";
import MFAModule from "./modules/mfa";
import AIModule from "./modules/ai";

/**
 * Primary navigation is organized around the project lifecycle
 * (SRS Section 7.1): Business Development -> Tenders -> Contracts ->
 * Planning -> Execution -> Procurement -> Financial Management ->
 * Client Billing -> Inventory/Equipment/Fuel/Workforce/Subcontractors,
 * with further modules (Company, Reports & AI, Admin) to be added
 * under AppShell's nav as they're built.
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/business-development" replace />} />
            <Route path="business-development/*" element={<BDCModule />} />
            <Route path="tenders/*" element={<TBMModule />} />
            <Route path="contracts" element={<ContractsPage />} />
            <Route path="contracts/:contractId" element={<ContractDetailPage />} />
            <Route path="planning/*" element={<PLNModule />} />
            <Route path="execution/*" element={<EXEModule />} />
            <Route path="procurement/*" element={<PRCModule />} />
            <Route path="finance/*" element={<FINModule />} />
            <Route path="billing/*" element={<BILModule />} />
            <Route path="inventory/*" element={<INVModule />} />
            <Route path="equipment/*" element={<EQPModule />} />
            <Route path="fuel/*" element={<FUELModule />} />
            <Route path="workforce/*" element={<WFMModule />} />
            <Route path="subcontractors/*" element={<SUBModule />} />
            <Route path="quality/*" element={<QMSModule />} />
            <Route path="hse/*" element={<HSEModule />} />
            <Route path="survey" element={<SVYModule />} />
            <Route path="plant-quarry" element={<PQModule />} />
            <Route path="project-controls" element={<PCModule />} />
            <Route path="assets" element={<ASTModule />} />
            <Route path="dashboard" element={<EXDModule />} />
            <Route path="client-portal" element={<CLPModule />} />
            <Route path="vendor-portal" element={<VNPModule />} />
            <Route path="mobile-sync" element={<MFAModule />} />
            <Route path="ai-assistant/*" element={<AIModule />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
