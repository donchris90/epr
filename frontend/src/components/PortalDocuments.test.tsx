import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PortalDocuments } from "./PortalDocuments";

const types = [{ value: "insurance", label: "Insurance" }, { value: "other", label: "Other" }];
const doc = { id: "d1", doc_type: "insurance", original_filename: "cover.pdf", content_type: "application/pdf", size_bytes: 2048, created_at: "2026-10-20T10:00:00Z" };

function setup(over: Partial<{ get: any; post: any }> = {}) {
  const get = over.get ?? vi.fn().mockResolvedValue({ data: { data: [] } });
  const post = over.post ?? vi.fn();
  render(<PortalDocuments client={{ get, post } as any} base="/vnp/vendor-users/u1" docTypes={types} />);
  return { get, post };
}

describe("PortalDocuments", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  it("shows an empty state, then lists documents with human sizes", async () => {
    setup();
    expect(await screen.findByText("No documents yet")).toBeInTheDocument();
  });

  it("lists existing documents", async () => {
    setup({ get: vi.fn().mockResolvedValue({ data: { data: [doc] } }) });
    expect(await screen.findByText("cover.pdf")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
    expect(screen.getByText("Insurance", { selector: "td" })).toBeInTheDocument();
  });

  it("requests a slot, PUTs the file to storage, confirms, and reloads", async () => {
    const get = vi.fn().mockResolvedValueOnce({ data: { data: [] } }).mockResolvedValueOnce({ data: { data: [doc] } });
    const post = vi.fn()
      .mockResolvedValueOnce({ data: { id: "d1", upload_url: "https://s3.example/put" } })
      .mockResolvedValueOnce({ data: {} });
    setup({ get, post });
    const file = new File(["%PDF"], "cover.pdf", { type: "application/pdf" });
    await userEvent.upload(await screen.findByLabelText("File"), file);
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(2));
    expect(post.mock.calls[0]).toEqual(["/vnp/vendor-users/u1/documents/upload-request", { original_filename: "cover.pdf", content_type: "application/pdf", doc_type: "insurance" }]);
    expect((fetch as any).mock.calls[0][0]).toBe("https://s3.example/put");
    expect(post.mock.calls[1][0]).toBe("/vnp/vendor-users/u1/documents/d1/confirm");
    expect(await screen.findByText("cover.pdf")).toBeInTheDocument();
  });

  it("does not confirm when the storage upload fails, and says so", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    const post = vi.fn().mockResolvedValueOnce({ data: { id: "d1", upload_url: "https://s3.example/put" } });
    setup({ post });
    await userEvent.upload(await screen.findByLabelText("File"), new File(["x"], "a.pdf", { type: "application/pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText(/upload to storage failed/i)).toBeInTheDocument();
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("shows the server's rejection (e.g. file type)", async () => {
    const post = vi.fn().mockRejectedValue({ response: { data: { title: "This file type is not allowed." } } });
    setup({ post });
    await userEvent.upload(await screen.findByLabelText("File"), new File(["x"], "a.pdf", { type: "application/pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByText(/not allowed/i)).toBeInTheDocument();
  });

  it("blocks files over the size limit before any request", async () => {
    const { post } = setup();
    const big = new File(["x"], "big.pdf", { type: "application/pdf" });
    Object.defineProperty(big, "size", { value: 21 * 1024 * 1024 });
    await userEvent.upload(await screen.findByLabelText("File"), big);
    expect(await screen.findByText("File too large")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
    expect(post).not.toHaveBeenCalled();
  });

  it("deletes only after a second confirming click, then reloads", async () => {
    const get = vi.fn().mockResolvedValueOnce({ data: { data: [doc] } }).mockResolvedValueOnce({ data: { data: [] } });
    const del = vi.fn().mockResolvedValue({});
    render(<PortalDocuments client={{ get, post: vi.fn(), delete: del } as any} base="/vnp/vendor-users/u1" docTypes={types} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete cover.pdf" }));
    expect(del).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/vnp/vendor-users/u1/documents/d1"));
    expect(await screen.findByText("No documents yet")).toBeInTheDocument();
  });

  it("cancel leaves the document alone", async () => {
    const del = vi.fn();
    render(<PortalDocuments client={{ get: vi.fn().mockResolvedValue({ data: { data: [doc] } }), post: vi.fn(), delete: del } as any} base="/b" docTypes={types} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete cover.pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(del).not.toHaveBeenCalled();
    expect(screen.getByText("cover.pdf")).toBeInTheDocument();
  });

  it("explains why a document in use can't be deleted", async () => {
    const del = vi.fn().mockRejectedValue({ response: { data: { title: "This document is attached to a claim or invoice you submitted, so it can't be deleted." } } });
    render(<PortalDocuments client={{ get: vi.fn().mockResolvedValue({ data: { data: [doc] } }), post: vi.fn(), delete: del } as any} base="/b" docTypes={types} />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete cover.pdf" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByText(/attached to a claim or invoice/i)).toBeInTheDocument();
    expect(screen.getByText("cover.pdf")).toBeInTheDocument();
  });
});

