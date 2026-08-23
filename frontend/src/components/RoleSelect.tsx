import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Select } from "./ui";

interface RoleOption {
  id: string;
  name: string;
}

/** Real role picker, backed by GET /v1/org/roles (app/org/routes.py)
 * -- the tenant's own real, dynamic roles (this codebase's RBAC
 * already supports arbitrary tenant-defined roles), same
 * value/onChange interface as ProjectSelect/UserSelect. */
export function RoleSelect({
  value,
  onChange,
  placeholder = "Select a role",
  required = false,
  id,
  ...rest
}: {
  value: string;
  onChange: (roleId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
} & Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "value" | "onChange" | "id" | "required">) {
  const [roles, setRoles] = useState<RoleOption[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/org/roles")
      .then((res) => setRoles(res.data.data))
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <Select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled>
        <option value="">Could not load roles</option>
      </Select>
    );
  }

  return (
    <Select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={roles === null} required={required} {...rest}>
      <option value="">{roles === null ? "Loading roles…" : placeholder}</option>
      {roles?.map((r) => (
        <option key={r.id} value={r.id}>
          {r.name}
        </option>
      ))}
    </Select>
  );
}
