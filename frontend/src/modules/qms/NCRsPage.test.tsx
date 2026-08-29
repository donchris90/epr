import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import NCRsPage from "./NCRsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const OPEN_NCR = { id: "ncr1", project_id: null, description: "Cracked slab", root_cause: null, disposition: null, status: "open", closed_at: null };

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NCRsPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [] } });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
});

describe("NCRsPage", () => {
  it("shows a real, honest empty state when there are no NCRs yet", async () => {
    renderPage();
    expect(await screen.findByText("No NCRs logged")).toBeInTheDocument();
  });

  it("logs a real corrective action linked to its real NCR via the real ncr_id field", async () => {
    /** Real regression test for a real bug: this page previously sent
     * `source_reference_id`, a field the real backend schema does not
     * have -- the real field is `ncr_id`. Every corrective action
     * logged from this page was silently created unlinked to its NCR,
     * which meant close_ncr's own real business rule ("cannot close
     * without a linked, verified corrective action") could never be
     * satisfied no matter what a real user did through this UI. */
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [OPEN_NCR] } });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Cracked slab");
    await user.type(screen.getByPlaceholderText("Corrective action"), "Repair and reinforce slab");
    await user.click(screen.getByRole("button", { name: /log action/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/corrective-actions", {
        source: "ncr",
        ncr_id: "ncr1",
        description: "Repair and reinforce slab",
      });
    });
    // Explicitly confirm the real bug's exact symptom cannot recur:
    // the payload must never contain the old, nonexistent field name.
    const [, payload] = vi.mocked(apiClient.post).mock.calls[0];
    expect(payload).not.toHaveProperty("source_reference_id");
  });

  it("dispositions a real open NCR via the real endpoint", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [OPEN_NCR] } });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Cracked slab");
    await user.selectOptions(screen.getByDisplayValue("Disposition…"), "rework");

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/ncrs/ncr1/disposition", { disposition: "rework" });
    });
  });

  it("closes a real NCR via the real endpoint", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [OPEN_NCR] } });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Cracked slab");
    await user.click(screen.getByRole("button", { name: /^close$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/ncrs/ncr1/close");
    });
  });

  it("shows the real business-rule error when a real NCR cannot yet be closed", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [OPEN_NCR] } });
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Cannot close NCR without a linked Corrective Action" } } });
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Cracked slab");
    await user.click(screen.getByRole("button", { name: /^close$/i }));

    expect(await screen.findByText("Cannot close NCR without a linked Corrective Action")).toBeInTheDocument();
  });

  it("logs a real new NCR via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No NCRs logged");

    await user.click(screen.getByRole("button", { name: /new ncr/i }));
    await user.type(screen.getByLabelText(/description/i), "Cracked slab in Block C");
    await user.click(screen.getByRole("button", { name: /log ncr/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/ncrs", { description: "Cracked slab in Block C", root_cause: "" });
    });
  });
});
