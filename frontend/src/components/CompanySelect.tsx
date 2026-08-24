import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface Company {
  id: string;
  name: string;
  functional_currency: string;
  is_default: boolean;
}

/** Real company picker, backed by GET /v1/fin/companies
 * (app/modules/fin/routes.py) -- replaces a raw "Company ID" text
 * input for real finance-posting flows. */
export function CompanySelect({
  value,
  onChange,
  placeholder = "Search companies…",
  required = false,
  id,
}: {
  value: string;
  onChange: (companyId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/fin/companies")
      .then((res) => setCompanies(res.data.data))
      .catch(() => setError(true));
  }, []);

  const options = companies?.map((c) => ({
    id: c.id,
    label: c.name,
    sublabel: [c.functional_currency, c.is_default ? "default" : null].filter(Boolean).join(" · "),
  }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && companies === null}
      error={error}
      errorMessage="Could not load companies"
      emptyMessage="No companies found"
      placeholder={placeholder}
      required={required}
      aria-label="Company"
    />
  );
}
