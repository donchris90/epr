import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MaterialApprovalsAndLabResultsPage from "./MaterialApprovalsAndLabResultsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MaterialApprovalsAndLabResultsPage />
    </QueryClientProvider>
  );
}

function mockGet(overrides: Record<string, unknown> = {}) {
  const responses: Record<string, unknown> = {
    "/qms/material-approvals": [],
    "/qms/lab-results": [],
    ...overrides,
  };
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url in responses) return Promise.resolve({ data: { data: responses[url] } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  mockGet();
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("MaterialApprovalsAndLabResultsPage", () => {
  it("shows real, honest empty states when there is genuinely nothing yet", async () => {
    renderPage();
    expect(await screen.findByText("No material approvals submitted yet.")).toBeInTheDocument();
    expect(screen.getByText("No lab results logged yet.")).toBeInTheDocument();
  });

  it("submits a real material approval via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No material approvals submitted yet.");

    await user.type(screen.getByPlaceholderText("Submittal reference"), "SUB-001");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/material-approvals", { submittal_reference: "SUB-001" });
    });
  });

  it("decides a real submitted material approval via the real endpoint", async () => {
    mockGet({ "/qms/material-approvals": [{ id: "ma1", material_item_id: null, submittal_reference: "SUB-002", status: "submitted", review_notes: null }] });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /^approve$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/material-approvals/ma1/decide", { decision: "approved", reviewNotes: undefined });
    });
  });

  it("does not show decide actions for a real already-decided approval", async () => {
    mockGet({ "/qms/material-approvals": [{ id: "ma1", material_item_id: null, submittal_reference: "SUB-003", status: "approved", review_notes: null }] });
    renderPage();

    await screen.findByText("SUB-003");
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it("lists a real lab result with its real value and threshold", async () => {
    mockGet({ "/qms/lab-results": [{ id: "lr1", pour_or_lot_reference: null, test_type: "concrete_cube_strength", sample_reference: null, tested_at: null, result_value: "35.5", unit: "MPa", acceptance_threshold: "30", pass_fail: null, lab_name: null }] });
    renderPage();

    expect(await screen.findByText(/35\.5/)).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
  });

  it("records a real pass outcome via the real endpoint", async () => {
    mockGet({ "/qms/lab-results": [{ id: "lr1", pour_or_lot_reference: null, test_type: "concrete_cube_strength", sample_reference: null, tested_at: null, result_value: "35.5", unit: "MPa", acceptance_threshold: "30", pass_fail: null, lab_name: null }] });
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /^pass$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/lab-results/lr1/record-outcome", { pass_fail: true });
    });
  });

  it("shows a real error banner when submitting a material approval fails", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Duplicate submittal reference" } } });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No material approvals submitted yet.");

    await user.type(screen.getByPlaceholderText("Submittal reference"), "SUB-004");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    expect(await screen.findByText("Duplicate submittal reference")).toBeInTheDocument();
  });
});
