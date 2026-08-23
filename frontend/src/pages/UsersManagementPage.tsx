import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient, getErrorMessage, getErrorStatus, getFieldErrors } from "../api/client";
import { PageHeader, Button, Card, Table, Th, Td, Badge, EmptyState, Input, Select, Field } from "../components/ui";
import { LoadingState } from "../components/Loading";
import { ErrorState } from "../components/ErrorState";
import { Modal } from "../components/Modal";
import { useToast } from "../lib/toast";
import { useUnsavedChanges } from "../lib/useUnsavedChanges";

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

/** Real invitation creation -- POST /v1/org/invitations, backed by
 * real seat-limit enforcement server-side (a 402 here is not a bug,
 * it's the plan's real limit, matching Phase 33's own point that the
 * frontend must never be the only enforcement layer). */
function InviteUserModal({ roles, onClose, onDone }: { roles: Role[]; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState(roles[0]?.id ?? "");
  const [department, setDepartment] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [message, setMessage] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [limitReached, setLimitReached] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isDirty = email.trim() !== "" || department.trim() !== "" || jobTitle.trim() !== "" || message.trim() !== "";
  useUnsavedChanges(isDirty && !submitting);

  async function submit() {
    const errors: Record<string, string> = {};
    if (!email.trim()) errors.email = "Email is required.";
    if (!roleId) errors.role = "Select a role.";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

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
      toast.success(`Invitation sent to ${email.trim()}.`);
      onDone();
    } catch (err) {
      if (getErrorStatus(err) === 402) {
        setLimitReached(getErrorMessage(err));
      } else {
        setFieldErrors(Object.fromEntries(getFieldErrors(err).map((f) => [f.field, f.message])));
        setError(getErrorMessage(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (limitReached) {
    return (
      <Modal title="User limit reached" onClose={onClose}>
        <div style={{ fontSize: 13, color: "var(--sf-navy-600)", marginBottom: 16 }}>{limitReached}</div>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <Button variant="secondary" onClick={onClose}>
            Manage Existing Users
          </Button>
          <Button onClick={() => (window.location.href = "/account/subscription")}>Upgrade Plan</Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="Invite User" onClose={onClose} confirmCloseIfDirty={isDirty && !submitting}>
      <Field label="Email" required error={fieldErrors.email}>
        <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com" />
      </Field>
      <Field label="Role" required error={fieldErrors.role}>
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
      {error && (
        <div role="alert" style={{ color: "var(--sf-brick)", fontSize: 12, marginTop: 8 }}>
          {error}
        </div>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <Button variant="secondary" onClick={onClose} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={submit} disabled={submitting}>
          {submitting ? "Sending…" : "Send Invitation"}
        </Button>
      </div>
    </Modal>
  );
}

export default function UsersManagementPage() {
  const toast = useToast();
  const [seats, setSeats] = useState<Seats | null>(null);
  const [users, setUsers] = useState<OrgUser[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[] | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [error, setError] = useState<unknown>(null);
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
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function userAction(action: "suspend" | "reactivate" | "remove", userId: string, label: string) {
    setPendingId(userId);
    try {
      await apiClient.post(`/org/users/${userId}/${action}`);
      toast.success(`${label} succeeded.`);
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  async function resendInvitation(id: string) {
    setPendingId(id);
    try {
      await apiClient.post(`/org/invitations/${id}/resend`);
      toast.success("Invitation resent.");
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  async function cancelInvitation(id: string) {
    setPendingId(id);
    try {
      await apiClient.post(`/org/invitations/${id}/cancel`);
      toast.success("Invitation canceled.");
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setPendingId(null);
    }
  }

  const activeCount = users?.length ?? 0;
  const pendingCount = invitations?.length ?? 0;
  const percentUsed = seats?.seat_limit ? Math.round((seats.seats_used / seats.seat_limit) * 100) : null;
  const atLimit = seats?.seat_limit != null && seats.seats_remaining != null && seats.seats_remaining <= 0;

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px" }}>
      <PageHeader
        eyebrow="Settings"
        title="Organization Users"
        action={
          <Button onClick={() => setShowInvite(true)} disabled={roles.length === 0 || atLimit}>
            + Invite User
          </Button>
        }
      />

      {seats && (
        <Card style={{ marginBottom: 20 }}>
          <div className="sf-grid-responsive" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: seats.seat_limit != null ? 12 : 0 }}>
            <div>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Seats included</div>
              <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{seats.seat_limit ?? "Unlimited"}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Active users</div>
              <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{activeCount}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>Pending invitations</div>
              <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700 }}>{pendingCount}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase" }}>
                {seats.seat_limit != null ? "Available after pending" : "Seats used"}
              </div>
              <div className="sf-mono" style={{ fontSize: 20, fontWeight: 700, color: atLimit ? "var(--sf-brick)" : undefined }}>
                {seats.seat_limit != null ? seats.seats_remaining ?? 0 : seats.seats_used}
              </div>
            </div>
          </div>
          {seats.seat_limit != null && percentUsed != null && (
            <div>
              <div style={{ height: 8, background: "var(--sf-paper-dim)", borderRadius: 999, overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${Math.min(percentUsed, 100)}%`,
                    background: atLimit ? "var(--sf-brick)" : percentUsed >= 80 ? "var(--sf-amber)" : "var(--sf-navy-900)",
                    transition: "width 0.2s",
                  }}
                />
              </div>
              <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginTop: 4 }}>{percentUsed}% of seats used</div>
            </div>
          )}
          {atLimit && (
            <div style={{ marginTop: 12, padding: "10px 12px", background: "var(--sf-brick-dim)", border: "1px solid var(--sf-brick)", borderRadius: "var(--sf-radius)", fontSize: 13 }}>
              You've used all available seats. <Link to="/account/subscription" style={{ color: "var(--sf-brick)", fontWeight: 600 }}>Upgrade your plan</Link> to invite more people.
            </div>
          )}
        </Card>
      )}

      <Card style={{ padding: 0, marginBottom: 20 }}>
        {error ? (
          <ErrorState error={error} onRetry={load} />
        ) : users === null ? (
          <LoadingState variant="table" label="Loading organization users" />
        ) : users.length === 0 && (invitations?.length ?? 0) === 0 ? (
          <EmptyState
            title="No organization members yet"
            hint="Invite your first teammate to get started."
            action={
              <Button onClick={() => setShowInvite(true)} disabled={roles.length === 0}>
                + Invite User
              </Button>
            }
          />
        ) : (
          <Table ariaLabel="Organization users and pending invitations">
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
                        <Button
                          variant="danger"
                          disabled={pendingId === u.id}
                          onClick={() => userAction("suspend", u.id, `Suspending ${u.email}`)}
                        >
                          Suspend
                        </Button>
                      )}
                      {u.status === "suspended" && (
                        <Button
                          variant="secondary"
                          disabled={pendingId === u.id}
                          onClick={() => userAction("reactivate", u.id, `Reactivating ${u.email}`)}
                        >
                          Reactivate
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        disabled={pendingId === u.id}
                        onClick={() => {
                          if (window.confirm(`Remove ${u.email} from the organization?`)) userAction("remove", u.id, `Removing ${u.email}`);
                        }}
                      >
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
