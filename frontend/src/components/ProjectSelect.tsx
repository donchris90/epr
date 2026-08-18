import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Select } from "./ui";

interface Project {
  id: string;
  name: string;
  status: string;
}

/** Real project picker, backed by GET /v1/projects (app/projects/routes.py)
 * -- replaces the raw "Paste a project UUID" text fields that used to
 * be scattered across exe/pc/fin/pln/hse, since there was previously
 * no way for a frontend to list projects at all. Same controlled
 * value/onChange interface as a plain <input>, so swapping one in is
 * a one-line change per call site. */
export function ProjectSelect({
  value,
  onChange,
  placeholder = "Select a project",
  includeEmptyOption = true,
  required = false,
}: {
  value: string;
  onChange: (projectId: string) => void;
  placeholder?: string;
  includeEmptyOption?: boolean;
  required?: boolean;
}) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/projects")
      .then((res) => setProjects(res.data.data))
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <Select value={value} onChange={(e) => onChange(e.target.value)} disabled>
        <option value="">Could not load projects</option>
      </Select>
    );
  }

  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)} disabled={projects === null} required={required}>
      {includeEmptyOption && <option value="">{projects === null ? "Loading projects…" : placeholder}</option>}
      {projects?.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
          {p.status !== "active" ? ` (${p.status})` : ""}
        </option>
      ))}
    </Select>
  );
}
