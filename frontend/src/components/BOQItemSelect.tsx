import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface BOQItem {
  id: string;
  item_code: string | null;
  description: string;
  unit: string | null;
}

/** Real BOQ item picker -- deliberately contract-scoped, not a flat
 * tenant-wide picker like the other entity selects. Confirmed
 * directly against the backend that there is no generic "list all
 * BOQ items" endpoint at all -- only GET
 * /v1/tbm/tenders/<tender_id>/boq-items, scoped to a parent tender.
 * A real, two-step resolve: GET /v1/ctm/contracts/<contractId> for
 * its own real tender_id (ContractSchema exposes it directly), then
 * the tender's own real BOQ items. Renders a real "select a contract
 * first" state rather than fetching nothing and pretending to be
 * ready. */
export function BOQItemSelect({
  contractId,
  value,
  onChange,
  placeholder = "Search BOQ items…",
  id,
}: {
  contractId: string;
  value: string;
  onChange: (boqItemId: string) => void;
  placeholder?: string;
  id?: string;
}) {
  const [items, setItems] = useState<BOQItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!contractId) {
      setItems(null);
      setError(false);
      return;
    }
    setItems(null);
    setError(false);
    apiClient
      .get(`/ctm/contracts/${contractId}`)
      .then((res) => apiClient.get(`/tbm/tenders/${res.data.tender_id}/boq-items`))
      .then((res) => setItems(res.data.data))
      .catch(() => setError(true));
  }, [contractId]);

  if (!contractId) {
    return (
      <Combobox
        id={id}
        value=""
        onChange={() => {}}
        options={[]}
        disabled
        placeholder="Select a contract first"
        clearable={false}
        aria-label="BOQ item"
      />
    );
  }

  const options = items?.map((item) => ({
    id: item.id,
    label: item.description,
    sublabel: [item.item_code, item.unit].filter(Boolean).join(" · ") || undefined,
  }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && items === null}
      error={error}
      errorMessage="Could not load BOQ items for this contract"
      emptyMessage="No BOQ items found for this contract"
      placeholder={placeholder}
      aria-label="BOQ item"
    />
  );
}
