import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DocumentLibraryPage from "./DocumentLibraryPage";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

const SAMPLE_DOCS = [
  {
    id: "d1",
    project_id: null,
    doc_type: "drawing",
    original_filename: "site-plan.pdf",
    content_type: "application/pdf",
    size_bytes: 204800,
    status: "uploaded",
    created_at: new Date().toISOString(),
  },
];

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <DocumentLibraryPage />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url === "/documents") return Promise.resolve({ data: { data: SAMPLE_DOCS } });
    if (url === "/projects") return Promise.resolve({ data: { data: [] } });
    if (url === "/documents/d1") return Promise.resolve({ data: { download_url: "https://s3.example.com/real-download-link" } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  vi.mocked(apiClient.delete).mockResolvedValue({ data: {} });
  vi.stubGlobal("open", vi.fn());
});

describe("DocumentLibraryPage", () => {
  it("lists real documents from the backend", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("site-plan.pdf")).toBeInTheDocument();
      expect(screen.getByText("200.0 KB")).toBeInTheDocument();
    });
  });

  it("shows a real empty state when there are no documents", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/documents") return Promise.resolve({ data: { data: [] } });
      if (url === "/projects") return Promise.resolve({ data: { data: [] } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/no documents yet/i)).toBeInTheDocument();
    });
  });

  it("downloading a ready document fetches and opens the real download URL", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("site-plan.pdf"));

    await user.click(screen.getByRole("button", { name: /download/i }));

    await waitFor(() => {
      expect(window.open).toHaveBeenCalledWith("https://s3.example.com/real-download-link", "_blank");
    });
  });

  it("calls the real delete endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("site-plan.pdf"));

    await user.click(screen.getByRole("button", { name: /delete/i }));

    await waitFor(() => {
      expect(apiClient.delete).toHaveBeenCalledWith("/documents/d1");
    });
  });

  it("a document still uploading cannot be downloaded", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url === "/documents")
        return Promise.resolve({ data: { data: [{ ...SAMPLE_DOCS[0], status: "pending" }] } });
      if (url === "/projects") return Promise.resolve({ data: { data: [] } });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    renderPage();
    await waitFor(() => screen.getByText("site-plan.pdf"));

    expect(screen.getByRole("button", { name: /download/i })).toBeDisabled();
  });
});
