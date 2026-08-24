import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Combobox } from "./Combobox";

interface Account {
  id: string;
  code: string;
  name: string;
  account_type: string;
  is_active: boolean;
}

/** Real chart-of-accounts picker, backed by GET /v1/fin/chart-of-accounts
 * (app/modules/fin/routes.py) -- replaces a raw "Account ID" text
 * input for the real journal-entry posting flows (e.g. WFM's own
 * "Post payroll to finance" action). */
export function AccountSelect({
  value,
  onChange,
  placeholder = "Search accounts…",
  required = false,
  id,
}: {
  value: string;
  onChange: (accountId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}) {
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/fin/chart-of-accounts")
      .then((res) => setAccounts(res.data.data))
      .catch(() => setError(true));
  }, []);

  const options = accounts
    ?.filter((a) => a.is_active)
    .map((a) => ({ id: a.id, label: a.name, sublabel: `${a.code} · ${a.account_type}` }));

  return (
    <Combobox
      id={id}
      value={value}
      onChange={onChange}
      options={error ? [] : options ?? null}
      loading={!error && accounts === null}
      error={error}
      errorMessage="Could not load accounts"
      emptyMessage="No accounts found"
      placeholder={placeholder}
      required={required}
      aria-label="Account"
    />
  );
}
