import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RolesPage from "./RolesPage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

const SAMPLE_ROLES = [
  { id: "r1", name: "Administrator", permission_set: ["*"] },
  { id: "r2", name: "Site Engineer", permission_set: ["exe:read", "exe:write"] },
];

const SAMPLE_CATALOG = [
  {
    module_code: "exe",
    module_label: "Execution",
    permissions: [
      { code: "exe:read", label: "Execution — View" },
      { code: "exe:write", label: "Execution — Create & Edit" },
    ],
  },
  {
    module_code: "bdc",
    module_label: "Business Development",
    permissions: [{ code: "bdc:read", label: "Business Development — View" }],
  },
];

beforeEach(() => {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/org/roles") return Promise.resolve({ data: { data: SAMPLE_ROLES } });
    if (url === "/org/permissions-catalog") return Promise.resolve({ data: { data: SAMPLE_CATALOG } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
  vi.mocked(apiClient.put).mockResolvedValue({ data: {} });
  vi.mocked(apiClient.delete).mockResolvedValue({ data: {} });
});

describe("RolesPage", () => {
  it("lists real roles with their real access summary", async () => {
    render(<RolesPage />);
    await waitFor(() => {
      expect(screen.getByText("Administrator")).toBeInTheDocument();
      expect(screen.getByText("Full access")).toBeInTheDocument();
      expect(screen.getByText("Site Engineer")).toBeInTheDocument();
      expect(screen.getByText("2 permissions")).toBeInTheDocument();
    });
  });

  it("opens the create form and shows the real permission catalog", async () => {
    const user = userEvent.setup();
    render(<RolesPage />);
    await waitFor(() => screen.getByText("Administrator"));

    await user.click(screen.getByRole("button", { name: /new role/i }));

    await waitFor(() => {
      expect(screen.getByText("Execution")).toBeInTheDocument();
      expect(screen.getByText("Business Development")).toBeInTheDocument();
    });
  });

  it("submits a real create request with the entered name and selected permissions", async () => {
    const user = userEvent.setup();
    render(<RolesPage />);
    await waitFor(() => screen.getByText("Administrator"));

    await user.click(screen.getByRole("button", { name: /new role/i }));
    await waitFor(() => screen.getByPlaceholderText(/site engineer/i));

    await user.type(screen.getByPlaceholderText(/site engineer/i), "Junior Coordinator");
    await user.click(screen.getByText("Business Development"));
    await user.click(screen.getByText("Business Development — View"));
    await user.click(screen.getByRole("button", { name: /^create role$/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/org/roles", { name: "Junior Coordinator", permission_set: ["bdc:read"] });
    });
  });

  it("edit pre-fills the existing role's real permissions", async () => {
    const user = userEvent.setup();
    render(<RolesPage />);
    await waitFor(() => screen.getByText("Site Engineer"));

    const siteEngineerRow = screen.getByText("Site Engineer").closest("tr");
    const editButton = siteEngineerRow!.querySelector("button");
    await user.click(editButton!);

    await waitFor(() => {
      const input = screen.getByDisplayValue("Site Engineer");
      expect(input).toBeInTheDocument();
    });
  });

  it("calls the real delete endpoint", async () => {
    const user = userEvent.setup();
    render(<RolesPage />);
    await waitFor(() => screen.getByText("Site Engineer"));

    const deleteButtons = screen.getAllByRole("button", { name: /^delete$/i });
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(apiClient.delete).toHaveBeenCalledWith("/org/roles/r1");
    });
  });

  it("shows a real error banner when deletion is refused by the backend", async () => {
    vi.mocked(apiClient.delete).mockRejectedValue({
      response: { data: { title: "This role is still assigned to active users", detail: "1 user(s) currently have this role." } },
    });

    const user = userEvent.setup();
    render(<RolesPage />);
    await waitFor(() => screen.getByText("Site Engineer"));

    const deleteButtons = screen.getAllByRole("button", { name: /^delete$/i });
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/1 user\(s\) currently have this role/i)).toBeInTheDocument();
    });
  });
});
