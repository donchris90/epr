import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PunchAndSnagListsPage from "./PunchAndSnagListsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  getErrorMessage: vi.fn((err: any) => err?.response?.data?.title || "Something went wrong."),
}));

const PROJECTS = [{ id: "p1", name: "Lekki Tower Phase 1", status: "active" }];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PunchAndSnagListsPage />
    </QueryClientProvider>
  );
}

function mockGet(overrides: Record<string, unknown> = {}) {
  const responses: Record<string, unknown> = {
    "/projects": PROJECTS,
    "/qms/punch-list-items": [],
    "/qms/snag-list-items": [],
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

describe("PunchAndSnagListsPage", () => {
  it("shows real, honest empty states when there is genuinely nothing yet", async () => {
    renderPage();
    expect(await screen.findByText("No punch list items yet.")).toBeInTheDocument();
    expect(screen.getByText("No snag list items yet.")).toBeInTheDocument();
  });

  it("lists a real punch list item and closes it via the real endpoint", async () => {
    mockGet({ "/qms/punch-list-items": [{ id: "pl1", project_id: "p1", area_building_section: "Block A", description: "Paint touch-up", status: "open" }] });
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Paint touch-up")).toBeInTheDocument();
    expect(screen.getByText("Block A")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^close$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/punch-list-items/pl1/close");
    });
  });

  it("does not show a close action for a real already-closed punch list item", async () => {
    mockGet({ "/qms/punch-list-items": [{ id: "pl1", project_id: "p1", area_building_section: null, description: "Done item", status: "closed" }] });
    renderPage();

    await screen.findByText("Done item");
    expect(screen.queryByRole("button", { name: /^close$/i })).not.toBeInTheDocument();
  });

  it("adds a real punch list item via the real endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No punch list items yet.");
    await screen.findAllByText("Lekki Tower Phase 1");
    await user.selectOptions(screen.getAllByRole("combobox")[0], "p1");
    const descriptionInputs = screen.getAllByDisplayValue("");
    await user.type(descriptionInputs[1], "Fix door handle");

    await user.click(screen.getAllByRole("button", { name: /^add$/i })[0]);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/punch-list-items", expect.objectContaining({ project_id: "p1", description: "Fix door handle" }));
    });
  });

  it("lists a real snag list item and closes it via the real endpoint", async () => {
    mockGet({ "/qms/snag-list-items": [{ id: "sl1", project_id: "p1", area_building_section: "Block B", description: "Loose tile", status: "open" }] });
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Loose tile")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^close$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/qms/snag-list-items/sl1/close");
    });
  });

  it("shows a real error banner when adding a punch list item fails", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({ response: { data: { title: "Project not found" } } });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("No punch list items yet.");
    await screen.findAllByText("Lekki Tower Phase 1");
    await user.selectOptions(screen.getAllByRole("combobox")[0], "p1");
    const descriptionInputs = screen.getAllByDisplayValue("");
    await user.type(descriptionInputs[1], "Something");
    await user.click(screen.getAllByRole("button", { name: /^add$/i })[0]);

    expect(await screen.findByText("Project not found")).toBeInTheDocument();
  });
});
