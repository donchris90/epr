import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ProjectsPage from "./ProjectsPage";
import { apiClient } from "../../api/client";

vi.mock("../../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const SAMPLE_PROJECTS = [
  { id: "p1", name: "Lekki Tower", status: "active", client_id: null, project_manager_id: null, start_date: "2026-01-15", end_date: null },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <ProjectsPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/projects") return Promise.resolve({ data: { data: SAMPLE_PROJECTS } });
    if (url === "/fin/companies") return Promise.resolve({ data: { data: [{ id: "c1", name: "Real Construction Co" }] } });
    if (url === "/bdc/clients") return Promise.resolve({ data: { data: [{ id: "cl1", name: "Test Client Ltd" }] } });
    if (url === "/org/members") return Promise.resolve({ data: { users: [{ id: "u1", email: "pm@example.com" }] } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: { id: "p2" } });
});

describe("ProjectsPage", () => {
  it("lists real projects from the backend", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Lekki Tower")).toBeInTheDocument();
    });
  });

  it("shows a real empty state when there are no projects", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/projects") return Promise.resolve({ data: { data: [] } });
      return Promise.resolve({ data: { data: [] } });
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
    });
  });

  it("opens the create modal and loads real company/client/PM options", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("Lekki Tower"));

    await user.click(screen.getByRole("button", { name: /new project/i }));

    await waitFor(() => {
      expect(screen.getByText("Real Construction Co")).toBeInTheDocument();
      expect(screen.getByText("Test Client Ltd")).toBeInTheDocument();
      expect(screen.getByText("pm@example.com")).toBeInTheDocument();
    });
  });

  it("submits a real create request with the entered name and selected company", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("Lekki Tower"));

    await user.click(screen.getByRole("button", { name: /new project/i }));
    await waitFor(() => screen.getByPlaceholderText(/lekki tower/i));

    await user.type(screen.getByPlaceholderText(/lekki tower/i), "New Real Project");
    await user.click(screen.getByRole("button", { name: /^create project$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/projects",
        expect.objectContaining({ name: "New Real Project", company_id: "c1" })
      );
    });
  });

  it("shows a real error, not a crash, when a dropdown's backend call fails", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/projects") return Promise.resolve({ data: { data: SAMPLE_PROJECTS } });
      if (url === "/fin/companies") return Promise.resolve({ data: { data: [{ id: "c1", name: "Real Construction Co" }] } });
      if (url === "/bdc/clients") return Promise.reject(new Error("403 Forbidden"));
      if (url === "/org/members") return Promise.resolve({ data: { users: [] } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });

    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("Lekki Tower"));
    await user.click(screen.getByRole("button", { name: /new project/i }));

    await waitFor(() => {
      expect(screen.getByText(/could not load clients/i)).toBeInTheDocument();
      // The rest of the form still works despite this one dropdown failing.
      expect(screen.getByText("Real Construction Co")).toBeInTheDocument();
    });
  });
});
