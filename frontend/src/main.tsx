import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
// Bootstrap's grid/layout system, loaded first so tokens.css's own
// rules (the existing color/type/component design system, built and
// tested earlier this session) correctly win via normal CSS cascade
// order -- Bootstrap provides real, responsive grid/flex utilities
// (container/row/col-*, d-flex, gap-*) used directly as classNames
// across the app now, not a full visual re-skin.
import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/tokens.css";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
