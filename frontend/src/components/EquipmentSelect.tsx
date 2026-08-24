import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface Equipment {
  id: string;
  name: string;
  make: string | null;
  model: string | null;
  serial_chassis_number: string | null;
}

/** Real equipment picker, backed by GET /v1/eqp/equipment
 * (app/modules/eqp/routes.py) -- replaces raw "Equipment ID" text
 * inputs. */
export function EquipmentSelect({
  value,
  onChange,
  placeholder = "Search equipment…",
  required = false,
  id,
}: {
  value: string;
  onChange: (equipmentId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [equipment, setEquipment] = useState<Equipment[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/eqp/equipment")
      .then((res) => setEquipment(res.data.data))
      .catch(() => setError(true));
  }, []);

  const options = equipment?.map((eq) => ({
    id: eq.id,
    label: eq.name,
    sublabel: [eq.make, eq.model, eq.serial_chassis_number].filter(Boolean).join(" ") || undefined,
  }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && equipment === null}
      error={error}
      errorMessage="Could not load equipment"
      emptyMessage="No equipment found"
      placeholder={placeholder}
      required={required}
      aria-label="Equipment"
    />
  );
}
