import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PortalOrgDocuments from "./PortalOrgDocuments";
import { apiClient } from "../api/client";

vi.mock("../api/client", () => ({
  apiClient: { get: vi.fn() },
  getErrorMessage: (e: any) => e?.response?.data?.title || "Something went wrong.",
}));

const ROW = (o: any = {}) => ({ id: "d1", doc_type: "certificate", original_filename: "licence.pdf", size_bytes: 2048, status: "uploaded", created_at: "2026-10-01T00:00:00Z", ...o });

beforeEach(() => vi.resetAllMocks());

describe("PortalOrgDocuments", () => {
  it("asks only for this organisation's portal documents", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [ROW()] } } as any);
    render(<PortalOrgDocuments source="vendor" ownerId="v1" name="Acme Steel" onClose={() => {}} />);
    expect(await screen.findByText("licence.pdf")).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/documents", { params: { source: "vendor", portal_owner_id: "v1" } });
    expect(screen.getByText("Documents uploaded by Acme Steel")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  it("uses the subcontractor source for subcontractors", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [] } } as any);
    render(<PortalOrgDocuments source="subcontractor" ownerId="s1" name="Sparks" onClose={() => {}} />);
    await screen.findByText("Nothing uploaded through the portal yet.");
    expect(apiClient.get).toHaveBeenCalledWith("/documents", { params: { source: "subcontractor", portal_owner_id: "s1" } });
  });

  it("downloads through the document's own link; unfinished uploads have none", async () => {
    vi.mocked(apiClient.get).mockImplementation((url: string) =>
      Promise.resolve({ data: url === "/documents/d1" ? { download_url: "https://files.example/d1" } : { data: [ROW(), ROW({ id: "d2", original_filename: "half.pdf", status: "pending" })] } } as any)
    );
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    const user = userEvent.setup();
    render(<PortalOrgDocuments source="vendor" ownerId="v1" name="Acme" onClose={() => {}} />);
    await user.click(await screen.findByRole("button", { name: "Download licence.pdf" }));
    await waitFor(() => expect(open).toHaveBeenCalledWith("https://files.example/d1", "_blank", "noopener"));
    expect(screen.queryByRole("button", { name: "Download half.pdf" })).toBeNull();
    open.mockRestore();
  });

  it("shows the permission error instead of an empty-looking panel", async () => {
    vi.mocked(apiClient.get).mockRejectedValue({ response: { data: { title: "Forbidden" } } });
    render(<PortalOrgDocuments source="vendor" ownerId="v1" name="Acme" onClose={() => {}} />);
    expect(await screen.findByText("Forbidden")).toBeInTheDocument();
  });

  it("closes", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [] } } as any);
    const onClose = vi.fn();
    render(<PortalOrgDocuments source="vendor" ownerId="v1" name="Acme" onClose={onClose} />);
    await userEvent.click(await screen.findByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalled();
  });
});
