import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import ProfilePage from "./ProfilePage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("../lib/auth", () => ({
  clearTokens: vi.fn(),
}));

const SAMPLE_PROFILE = {
  id: "u1",
  email: "profile-test@example.com",
  status: "active",
  department: "Engineering",
  job_title: "Site Engineer",
  avatar_url: null,
};

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiClient.get).mockResolvedValue({ data: SAMPLE_PROFILE });
  vi.mocked(apiClient.put).mockResolvedValue({ data: { ...SAMPLE_PROFILE, avatar_url: "https://real-avatar-url.example.com/img.jpg" } });
  vi.mocked(apiClient.delete).mockResolvedValue({ data: { ...SAMPLE_PROFILE, avatar_url: null } });
});

describe("ProfilePage", () => {
  it("shows real profile fields from the backend", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByDisplayValue("profile-test@example.com")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Engineering")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Site Engineer")).toBeInTheDocument();
    });
  });

  it("shows an email-initial placeholder when there is no avatar yet", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("P")).toBeInTheDocument(); // first letter of "profile-test@..."
    });
  });

  it("rejects a non-image file before any real upload is attempted", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Upload photo"));

    // fireEvent.change directly, not userEvent.upload -- upload()
    // respects the input's accept attribute the same way a real
    // browser's file picker dialog would, silently filtering out a
    // non-matching file before it ever reaches the component. This
    // test is specifically about the component's OWN validation
    // logic (the real defense-in-depth check, since a real user could
    // still bypass a picker dialog via drag-and-drop).
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const fakePdf = new File(["not an image"], "resume.pdf", { type: "application/pdf" });
    Object.defineProperty(fileInput, "files", { value: [fakePdf], configurable: true });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(screen.getByText(/please choose a real image file/i)).toBeInTheDocument();
    });
    expect(apiClient.put).not.toHaveBeenCalled();
  });

  it("shows the Remove button once a real avatar exists", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { ...SAMPLE_PROFILE, avatar_url: "https://real-avatar.example.com/x.jpg" } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Remove")).toBeInTheDocument();
      expect(screen.getByText("Change photo")).toBeInTheDocument();
    });
  });

  it("calls the real delete endpoint when removing the avatar", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { ...SAMPLE_PROFILE, avatar_url: "https://real-avatar.example.com/x.jpg" } });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("Remove"));

    await user.click(screen.getByText("Remove"));

    await waitFor(() => {
      expect(apiClient.delete).toHaveBeenCalledWith("/auth/me/avatar");
    });
  });
});

describe("ProfilePage — change password", () => {
  it("submits the real change-password request with all three fields", async () => {
    vi.mocked(apiClient.put).mockResolvedValue({ data: { message: "Password changed successfully." } });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("heading", { name: "Change password" }));

    await user.type(screen.getByLabelText(/current password/i), "originalpassword123");
    await user.type(screen.getByLabelText(/^new password/i), "brandnewpassword456");
    await user.type(screen.getByLabelText(/confirm new password/i), "brandnewpassword456");
    await user.click(screen.getByRole("button", { name: /^change password$/i }));

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith("/auth/me/password", {
        current_password: "originalpassword123",
        new_password: "brandnewpassword456",
      });
    });
  });

  it("blocks submission client-side when new passwords do not match", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("heading", { name: "Change password" }));

    await user.type(screen.getByLabelText(/current password/i), "originalpassword123");
    await user.type(screen.getByLabelText(/^new password/i), "brandnewpassword456");
    await user.type(screen.getByLabelText(/confirm new password/i), "somethingelse789");
    await user.click(screen.getByRole("button", { name: /^change password$/i }));

    expect(screen.getByText(/do not match/i)).toBeInTheDocument();
    expect(apiClient.put).not.toHaveBeenCalled();
  });

  it("shows the real backend error for a wrong current password", async () => {
    vi.mocked(apiClient.put).mockRejectedValue({ response: { data: { title: "Current password is incorrect" } } });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("heading", { name: "Change password" }));

    await user.type(screen.getByLabelText(/current password/i), "wrongpassword");
    await user.type(screen.getByLabelText(/^new password/i), "brandnewpassword456");
    await user.type(screen.getByLabelText(/confirm new password/i), "brandnewpassword456");
    await user.click(screen.getByRole("button", { name: /^change password$/i }));

    await waitFor(() => {
      expect(screen.getByText("Current password is incorrect")).toBeInTheDocument();
    });
  });

  it("shows a real success state mentioning being signed out, and clears tokens", async () => {
    vi.mocked(apiClient.put).mockResolvedValue({ data: { message: "Password changed successfully." } });
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("heading", { name: "Change password" }));

    await user.type(screen.getByLabelText(/current password/i), "originalpassword123");
    await user.type(screen.getByLabelText(/^new password/i), "brandnewpassword456");
    await user.type(screen.getByLabelText(/confirm new password/i), "brandnewpassword456");
    await user.click(screen.getByRole("button", { name: /^change password$/i }));

    await waitFor(() => {
      expect(screen.getByText(/you'll be signed out shortly/i)).toBeInTheDocument();
    });
  });
});
