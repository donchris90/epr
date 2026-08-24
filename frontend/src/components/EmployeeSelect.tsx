import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface Employee {
  id: string;
  name: string;
  employee_number: string | null;
  status: string;
}

/** Real employee picker, backed by GET /v1/wfm/employees
 * (app/modules/wfm/routes.py) -- a distinct, real Employee model
 * (permanent/contract staff, workforce management), not the internal
 * staff User account. Replaces raw "Employee ID" text inputs. */
export function EmployeeSelect({
  value,
  onChange,
  placeholder = "Search employees…",
  required = false,
  id,
}: {
  value: string;
  onChange: (employeeId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [employees, setEmployees] = useState<Employee[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/wfm/employees")
      .then((res) => setEmployees(res.data.data))
      .catch(() => setError(true));
  }, []);

  const options = employees?.map((e) => ({
    id: e.id,
    label: e.name,
    sublabel: [e.employee_number, e.status !== "active" ? e.status : null].filter(Boolean).join(" · ") || undefined,
  }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && employees === null}
      error={error}
      errorMessage="Could not load employees"
      emptyMessage="No employees found"
      placeholder={placeholder}
      required={required}
      aria-label="Employee"
    />
  );
}
