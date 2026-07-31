import { useMutation } from "@tanstack/react-query";
import axios from "axios";
import { apiClient } from "./client";

/**
 * Shared file-upload flow for every module that references a
 * document_id (vendor compliance docs, invoice uploads, ITP records,
 * and more) -- backed by real S3-compatible storage
 * (backend/app/documents/). The pattern is deliberately NOT "send the
 * file bytes to our own API": the browser uploads directly to S3 via
 * a presigned URL, and this app server only ever handles metadata.
 *
 * useUploadDocument() gives back a single mutate(file) call that
 * handles all three real HTTP round-trips (request an upload slot,
 * PUT the actual bytes, confirm) and resolves with the finished
 * Document's id -- the one thing most callers actually need, to
 * attach to whatever record they're building (a compliance document,
 * an invoice upload, etc).
 */
export function useUploadDocument() {
  return useMutation({
    mutationFn: async ({
      file,
      docType,
      projectId,
    }: {
      file: File;
      docType?: string;
      projectId?: string;
    }) => {
      const { data: uploadRequest } = await apiClient.post("/documents/upload-request", {
        original_filename: file.name,
        content_type: file.type || "application/octet-stream",
        doc_type: docType,
        project_id: projectId,
      });

      // A plain axios call, not apiClient -- this goes straight to S3
      // (or the local S3-compatible endpoint in dev), not through our
      // own API, and shouldn't carry an Authorization header meant for
      // our backend or get retried by the auth-refresh interceptor.
      await axios.put(uploadRequest.upload_url, file, {
        headers: { "Content-Type": file.type || "application/octet-stream" },
      });

      const { data: confirmed } = await apiClient.post(`/documents/${uploadRequest.id}/confirm`);
      return confirmed as { id: string; status: string; size_bytes: number };
    },
  });
}
