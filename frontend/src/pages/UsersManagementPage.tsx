import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { apiClient } from "../api/client";
import {
  PageHeader,
  Button,
  Card,
  Table,
  Th,
  Td,
  Badge,
  ErrorBanner,
  EmptyState,
  Input,
  Select,
  Field,
} from "../components/ui";

interface Role {
  id: string;
  name: string;
}

interface OrgUser {
  id: string;
  email: string;
  status: string;
  department: string | null;
  job_title: string | null;
  role: Role | null;
  created_at: string;
}

interface Invitation {
  id: string;
  email: string;
  status: string;
  department: string | null;
  job_title: string | null;
  role: Role | null;
  expires_at: string;
  created_at: string;
}

interface Seats {
  seat_limit: number | null;
  seats_used: number;
  seats_remaining: number | null;
}

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong.";
}

function statusBadge(status: string) {
  const tones: Record<string, "green" | "brick" | "neutral"> = {
    active: "green",
    pending: "neutral",
    suspended: "brick",
    disabled: "brick",
  };
  const labels: Record<string, string> = {
    active: "Active",
    pending: "Pending Invitation",
    suspended: "Suspended",
    disabled: "Disabled",
  };
  return <Badge tone={tones[status] ?? "neutral"}>{labels[status] ?? status}</Badge>;
}

/** Overlay -- this app has no shared Modal component yet; see
 * PlatformAdminTenantsPage.tsx's identical local Overlay for the same
 * reasoning (one screen's worth of usage isn't reason enough to
 * invent a generic one). */
function Overlay({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(11, 18, 27, 0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ width: 420 }}>
        <Card>{children}</Card>
      </div>
    </div>
  );
}

/** Real invitation creation -- POST /v1/org/invitations, backed by
 * real seat-limit enforcement server-side (a 402 here is not a bug,
 * it's the plan's real limit, matching Phase 33's own point that the
 * frontend must never be the only enforcement layer). */
function InviteUserModal({ roles, onClose, onDone }: { roles: Role[]; onClose: () => void; onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState(roles[0]?.id ?? "");
  const [department, setDepartment] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [limitReached, setLimitReached] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!email.trim() || !roleId) {
      setError("Email and role are required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    setLimitReached(null);
    try {
      await apiClient.post("/org/invitations", {
        email: email.trim(),
        role_id: roleId,
        department: department.trim() || undefined,
        job_title: jobTitle.trim() || undefined,
        message: message.trim() || undefined,
      });
      onDone();
    } catch (err: any) {
      if (err?.response?.status === 402) {
        setLimitReached(getErrorMessage(err));
      } else {
        setError(getErrorMessage(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (limitReached) {
    return (
      <Overlay onClose={onClose}>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>User limit reached</div>
        <div style={{ fontSize: 13, color: "var(--sf-navy-600)", marginBottom: 16 }}>{limitReached}</div>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <Button variant="secondary" onClick={onClose}>
            Manage Existing Users
          </Button>
          <Button onClick={() => (window.location.href = "/account/subscription")}>Upgrade Plan</Button>
        </div>
      </Overlay>
    );
  }

  return (
    <Overlay onClose={onClose}>
      <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 16 }}>Invite User</div>
      <Field label="Email">
        <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com" />
      </Field>
      <Field label="Role">
        <Select value={roleId} onChange={(e) => setRoleId(e.target.value)}>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Department (optional)">
        <Input value={department} onChange={(e) => setDepartment(e.target.value)} />
      </Field>
      <Field label="Job title (optional)">
        <Input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} />
      </Field>
      <Field label="Message (optional)">
        <Input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Welcome to the team..." />
      </Field>
      {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginTop: 8 }}>{error}</div>}
      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <Button variant="secondary" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={submitting}>
          {submitting ? "Sending…" : "Send Invitation"}
        </Button>
      </div>
    </Overlay>
  );
}

export default function UsersManagementPage() {
  const [seats, setSeats] = useState<Seats | null>(null);
  const [users, setUsers] = useState<OrgUser[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[] | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [showInvite, setShowInvite] = useState(false);

  async function load() {
    setError(null);
    try {
      const [seatsRes, membersRes, rolesRes] = await Promise.all([
        apiClient.get("/org/seats"),
        apiClient.get("/org/members"),
        apiClient.get("/org/roles"),
      ]);
      setSeats(seatsRes.data);
      setUsers(membersRes.data.users);
      setInvitations(membersRes.data.pending_invitations);
      setRoles(rolesRes.data.data);
    } catch (err: any) {
      setError(getErrorMessage(err));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function userAction(action: "suspend" | "reactivate" | "remove", userId: string) {
    setPendingId(userId);
    setError(null);
    try {
      await apiClient.post(`/org/users/${userId}/${action}`);
      await load();
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  async function resendInvitation(id: string) {
    setPendingId(id);
    setError(null);
    try {
      await apiClient.post(`/org/invitations/${id}/resend`);
      await load();
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  async function cancelInvitation(id: string) {
    setPendingId(id);
    setError(null);
    try {
      await apiClient.post(`/org/invitations/${id}/cancel`);
      await load();
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  const seatsText =
    seats?.seat_limit == null ? `${seats?.seats_used ?? 0} users (unlimited)` : `${seats.seats_used} / ${seats.seat_limit} seats used`;
  const remainingText = seats?.seat_limit == null ? null : `${seats?.seats_remaining ?? 0} seats remaining`;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader
        eyebrow="Settings"
        title="Organization Users"
        action={
          <Button onClick={() => setShowInvite(true)} disabled={roles.length === 0}>
            + Invite User
          </Button>
        }
      />

      {seats && (
        <div style={{ display: "flex", gap: 16, alignItems: "baseline", marginBottom: 20 }}>
          <span className="sf-mono" style={{ fontSize: 13 }}>
            {seatsText}
          </span>
          {remainingText && <span style={{ fontSize: 13, color: "var(--sf-navy-400)" }}>{remainingText}</span>}
        </div>
      )}

      {error && <ErrorBanner title="Something went wrong" detail={error} onDismiss={() => setError(null)} />}

      <Card style={{ padding: 0, marginBottom: 20 }}>
        {users === null ? (
          <div style={{ padding: 24, fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</div>
        ) : users.length === 0 && (invitations?.length ?? 0) === 0 ? (
          <EmptyState title="No organization members yet" hint="Invite your first teammate to get started." />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Email</Th>
                <Th>Role</Th>
                <Th>Department</Th>
                <Th>Status</Th>
                <Th>Joined</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id}>
                  <Td>{u.email}</Td>
                  <Td>{u.role?.name ?? "—"}</Td>
                  <Td>{u.department || "—"}</Td>
                  <Td>{statusBadge(u.status)}</Td>
                  <Td mono>{new Date(u.created_at).toLocaleDateString()}</Td>
                  <Td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      {u.status === "active" && (
                        <Button variant="danger" disabled={pendingId === u.id} onClick={() => userAction("suspend", u.id)}>
                          Suspend
                        </Button>
                      )}
                      {u.status === "suspended" && (
                        <Button variant="secondary" disabled={pendingId === u.id} onClick={() => userAction("reactivate", u.id)}>
                          Reactivate
                        </Button>
                      )}
                      <Button variant="ghost" disabled={pendingId === u.id} onClick={() => userAction("remove", u.id)}>
                        Remove
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
              {invitations?.map((inv) => (
                <tr key={inv.id}>
                  <Td>{inv.email}</Td>
                  <Td>{inv.role?.name ?? "—"}</Td>
                  <Td>{inv.department || "—"}</Td>
                  <Td>{statusBadge("pending")}</Td>
                  <Td mono>Expires {new Date(inv.expires_at).toLocaleDateString()}</Td>
                  <Td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      <Button variant="ghost" disabled={pendingId === inv.id} onClick={() => resendInvitation(inv.id)}>
                        Resend
                      </Button>
                      <Button variant="danger" disabled={pendingId === inv.id} onClick={() => cancelInvitation(inv.id)}>
                        Cancel
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {showInvite && (
        <InviteUserModal
          roles={roles}
          onClose={() => setShowInvite(false)}
          onDone={() => {
            setShowInvite(false);
            load();
          }}
        />
      )}
    </div>
  );
}
