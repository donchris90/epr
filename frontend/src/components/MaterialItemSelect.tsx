import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface MaterialItem {
  id: string;
  code: string;
  description: string;
  unit: string | null;
}

/** Real material item picker, backed by GET /v1/inv/material-items
 * (app/modules/inv/routes.py) -- a real, tenant-wide catalog, not
 * scoped to a specific warehouse (MaterialItemSchema has no
 * warehouse_id at all -- warehouse-specific data is stock levels, a
 * separate concept). Replaces raw "Material Item ID" / "BOQ item
 * UUID" text inputs used for the material catalog. */
export function MaterialItemSelect({
  value,
  onChange,
  placeholder = "Search material items…",
  required = false,
  id,
}: {
  value: string;
  onChange: (materialItemId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [items, setItems] = useState<MaterialItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/inv/material-items")
      .then((res) => setItems(res.data.data))
      .catch(() => setError(true));
  }, []);

  const options = items?.map((m) => ({
    id: m.id,
    label: m.description,
    sublabel: [m.code, m.unit].filter(Boolean).join(" · ") || undefined,
  }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && items === null}
      error={error}
      errorMessage="Could not load material items"
      emptyMessage="No material items found"
      placeholder={placeholder}
      required={required}
      aria-label="Material item"
    />
  );
}
