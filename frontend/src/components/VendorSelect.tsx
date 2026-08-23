import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface Vendor {
  id: string;
  name: string;
  status: string;
}

/** Real vendor picker, backed by GET /v1/prc/vendors
 * (app/modules/prc/routes.py) -- replaces raw "Vendor ID" text
 * inputs. Built on the shared Combobox primitive for real search and
 * keyboard navigation, not a plain <select>. */
export function VendorSelect({
  value,
  onChange,
  placeholder = "Search vendors…",
  required = false,
  id,
}: {
  value: string;
  onChange: (vendorId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [vendors, setVendors] = useState<Vendor[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/prc/vendors")
      .then((res) => setVendors(res.data.data))
      .catch(() => setError(true));
  }, []);

  const options = vendors?.map((v) => ({
    id: v.id,
    label: v.name,
    sublabel: v.status !== "active" ? v.status : undefined,
  }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && vendors === null}
      error={error}
      errorMessage="Could not load vendors"
      emptyMessage="No vendors found"
      placeholder={placeholder}
      required={required}
      aria-label="Vendor"
    />
  );
}
