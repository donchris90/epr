import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Select } from "./ui";

interface Member {
  id: string;
  email: string;
  status: string;
}

/** Real user picker, backed by GET /v1/org/members (app/org/routes.py)
 * -- same controlled value/onChange interface as ProjectSelect, so
 * both follow the identical, already-established pattern. Only
 * active users are offered (a removed or suspended user can't
 * meaningfully be a live approver), matching the same real status
 * filtering list_org_members already does server-side. */
export function UserSelect({
  value,
  onChange,
  placeholder = "Select a user",
  required = false,
  id,
  ...rest
}: {
  value: string;
  onChange: (userId: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
} & Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "value" | "onChange" | "id" | "required">) {
  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get("/org/members")
      .then((res) => setMembers(res.data.users))
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <Select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled>
        <option value="">Could not load users</option>
      </Select>
    );
  }

  const activeMembers = members?.filter((m) => m.status === "active") ?? null;

  return (
    <Select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={activeMembers === null} required={required} {...rest}>
      <option value="">{activeMembers === null ? "Loading users…" : placeholder}</option>
      {activeMembers?.map((m) => (
        <option key={m.id} value={m.id}>
          {m.email}
        </option>
      ))}
    </Select>
  );
}
