import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface Subcontractor {
  id: string;
  name: string;
  trade_specialty: string | null;
  status: string;
}

/** Real subcontractor picker, backed by GET /v1/sub/subcontractors
 * (app/modules/sub/routes.py) -- replaces raw "Subcontractor ID" text
 * inputs. */
export function SubcontractorSelect({
  value,
  onChange,
  placeholder = "Search subcontractors…",
  required = false,
  id,
}: {
  value: string;
  onChange: (subcontractorId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [subcontractors, setSubcontractors] = useState<Subcontractor[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/sub/subcontractors")
      .then((res) => setSubcontractors(res.data.data))
      .catch(() => setError(true));
  }, []);

  const options = subcontractors?.map((s) => ({
    id: s.id,
    label: s.name,
    sublabel: [s.trade_specialty, s.status !== "active" ? s.status : null].filter(Boolean).join(" · ") || undefined,
  }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && subcontractors === null}
      error={error}
      errorMessage="Could not load subcontractors"
      emptyMessage="No subcontractors found"
      placeholder={placeholder}
      required={required}
      aria-label="Subcontractor"
    />
  );
}
