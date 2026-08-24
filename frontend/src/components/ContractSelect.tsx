import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface Contract {
  id: string;
  contract_number: string;
  status: string;
  contract_value: string;
  currency: string;
}

/** Real contract picker, backed by GET /v1/ctm/contracts
 * (app/modules/ctm/routes.py) -- replaces raw "Contract ID" text
 * inputs. */
export function ContractSelect({
  value,
  onChange,
  placeholder = "Search contracts…",
  required = false,
  id,
}: {
  value: string;
  onChange: (contractId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/ctm/contracts")
      .then((res) => setContracts(res.data.data))
      .catch(() => setError(true));
  }, []);

  const options = contracts?.map((c) => ({
    id: c.id,
    label: c.contract_number,
    sublabel: `${c.currency} ${Number(c.contract_value).toLocaleString()}${c.status ? ` · ${c.status}` : ""}`,
  }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && contracts === null}
      error={error}
      errorMessage="Could not load contracts"
      emptyMessage="No contracts found"
      placeholder={placeholder}
      required={required}
      aria-label="Contract"
    />
  );
}
