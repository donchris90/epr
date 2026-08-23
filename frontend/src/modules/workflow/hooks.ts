import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../../api/client";
import type { WorkflowDefinition, WorkflowInstance, WorkflowStep } from "./types";

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

/** Real list, backed by GET /v1/workflow/definitions -- supports the
 * real, backend-provided module_name/entity_type filters; search and
 * status filtering happen client-side over the fetched set, since the
 * backend doesn't offer a text-search or active-only query param. */
export function useWorkflowDefinitions(filters?: { module_name?: string; entity_type?: string }) {
  const [definitions, setDefinitions] = useState<WorkflowDefinition[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Deliberately narrower than the full filters object: callers commonly
  // pass a new object literal each render (e.g. moduleFilter ?
  // {module_name: ...} : undefined in WorkflowListPage), which would
  // otherwise re-trigger this on every render even when the actual
  // filter values haven't changed.
  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    apiClient
      .get("/workflow/definitions", { params: filters })
      .then((res) => setDefinitions(res.data.data))
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters?.module_name, filters?.entity_type]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { definitions, loading, error, reload };
}

export function useWorkflowDefinition(id: string | undefined) {
  const [definition, setDefinition] = useState<WorkflowDefinition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    apiClient
      .get(`/workflow/definitions/${id}`)
      .then((res) => setDefinition(res.data))
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { definition, loading, error, reload };
}

/** Real create, backed by POST /v1/workflow/definitions -- always
 * creates a new, inactive version (see app/workflow/services.py's own
 * docstring: "Inactive by default so a definition can be built and
 * reviewed without immediately affecting live entities"). There is no
 * update/edit endpoint at all -- see docs/WORKFLOW_BUILDER_GAPS.md
 * for the full reasoning; "editing" a workflow in this UI always
 * means creating the next version, never true in-place mutation. */
export async function createWorkflowDefinition(input: {
  module_name: string;
  entity_type: string;
  workflow_name: string;
  description?: string;
  steps: WorkflowStep[];
}): Promise<WorkflowDefinition> {
  const res = await apiClient.post("/workflow/definitions", input);
  return res.data;
}

export async function activateWorkflowDefinition(id: string): Promise<WorkflowDefinition> {
  const res = await apiClient.post(`/workflow/definitions/${id}/activate`);
  return res.data;
}

export async function deactivateWorkflowDefinition(id: string): Promise<WorkflowDefinition> {
  const res = await apiClient.post(`/workflow/definitions/${id}/deactivate`);
  return res.data;
}

/** Real version history for one (module_name, entity_type) pair --
 * built entirely from the existing, real GET /v1/workflow/definitions
 * filters, since old inactive versions are never deleted
 * (app/workflow/services.py's own docstring: "keeping old inactive
 * versions around is deliberate"). No dedicated "history" endpoint
 * exists or is needed -- this is genuinely real data, not a
 * synthesized approximation. */
export async function getWorkflowVersionHistory(moduleName: string, entityType: string): Promise<WorkflowDefinition[]> {
  const res = await apiClient.get("/workflow/definitions", {
    params: { module_name: moduleName, entity_type: entityType },
  });
  return (res.data.data as WorkflowDefinition[]).sort((a, b) => b.version - a.version);
}

export function useWorkflowInstances(filters?: { module_name?: string; entity_type?: string; status?: string }) {
  const [instances, setInstances] = useState<WorkflowInstance[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Deliberately narrower than the full filters object, same reasoning
  // as useWorkflowDefinitions above.
  useEffect(() => {
    apiClient
      .get("/workflow/instances", { params: filters })
      .then((res) => setInstances(res.data.data))
      .catch((err) => setError(getErrorMessage(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters?.module_name, filters?.entity_type, filters?.status]);

  return { instances, error };
}
