import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface Warehouse {
  id: string;
  name: string;
  warehouse_type: string;
  location: string | null;
}

/** Real warehouse picker, backed by GET /v1/inv/warehouses
 * (app/modules/inv/routes.py) -- replaces raw "Warehouse ID" text
 * inputs. */
export function WarehouseSelect({
  value,
  onChange,
  placeholder = "Search warehouses…",
  required = false,
  id,
}: {
  value: string;
  onChange: (warehouseId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [warehouses, setWarehouses] = useState<Warehouse[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/inv/warehouses")
      .then((res) => setWarehouses(res.data.data))
      .catch(() => setError(true));
  }, []);

  const options = warehouses?.map((w) => ({
    id: w.id,
    label: w.name,
    sublabel: [w.warehouse_type, w.location].filter(Boolean).join(" · ") || undefined,
  }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && warehouses === null}
      error={error}
      errorMessage="Could not load warehouses"
      emptyMessage="No warehouses found"
      placeholder={placeholder}
      required={required}
      aria-label="Warehouse"
    />
  );
}
