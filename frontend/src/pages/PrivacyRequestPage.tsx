import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../api/client";
import { Button, Input, Select, Textarea, Field } from "../components/ui";
import { LegalLayout } from "./legal/LegalLayout";

const TYPES: { value: string; label: string }[] = [
  { value: "access", label: "Access — a copy of the personal data you hold about me" },
  { value: "portability", label: "Portability — my data in a portable format" },
  { value: "correction", label: "Correction — fix inaccurate data about me" },
  { value: "erasure", label: "Erasure — delete my personal data" },
  { value: "restriction", label: "Restriction — limit how my data is used" },
  { value: "objection", label: "Objection — I object to how my data is used" },
];

function msg(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Something went wrong. Please try again.";
}

/** Public form (no sign-in) for a person to make a data protection request
 * to a company that uses SiteForge. The company is identified by the id in
 * the link it publishes. Backed by /v1/public/privacy/<tenant>/requests. */
export default function PrivacyRequestPage() {
  const { tenantId } = useParams();
  const [company, setCompany] = useState<{ company_name: string; response_days: number } | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [form, setForm] = useState({ request_type: "access", subject_name: "", subject_email: "", subject_phone: "", details: "", website: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    apiClient
      .get(`/public/privacy/${tenantId}`)
      .then((r) => setCompany(r.data))
      .catch(() => setNotFound(true));
  }, [tenantId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await apiClient.post(`/public/privacy/${tenantId}/requests`, {
        request_type: form.request_type,
        subject_name: form.subject_name.trim(),
        subject_email: form.subject_email.trim(),
        subject_phone: form.subject_phone.trim() || null,
        details: form.details.trim() || null,
        website: form.website,
      });
      setDone(true);
    } catch (err) {
      setError(msg(err));
    } finally {
      setBusy(false);
    }
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<any>) => setForm({ ...form, [k]: e.target.value });

  return (
    <LegalLayout title="Make a data protection request">
      {notFound ? (
        <p>This request link isn't valid. Please check the link you were given, or contact the company directly.</p>
      ) : !company ? (
        <p>Loading…</p>
      ) : done ? (
        <div role="status">
          <p>
            <strong>Thank you.</strong> We've emailed you a confirmation link — please open it to confirm the request is yours. {company.company_name} aims to
            respond within {company.response_days} days.
          </p>
        </div>
      ) : (
        <form onSubmit={submit}>
          <p style={{ marginBottom: 14 }}>
            Ask <strong>{company.company_name}</strong> about the personal data it holds on you. We'll email you to confirm it's really you before anyone
            acts on your request.
          </p>
          <Field label="What would you like to do?">
            <Select value={form.request_type} onChange={set("request_type")}>
              {TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Your name">
            <Input required value={form.subject_name} onChange={set("subject_name")} />
          </Field>
          <Field label="Your email">
            <Input required type="email" value={form.subject_email} onChange={set("subject_email")} />
          </Field>
          <Field label="Phone (optional)">
            <Input value={form.subject_phone} onChange={set("subject_phone")} />
          </Field>
          <Field label="Anything else we should know (optional)">
            <Textarea maxLength={4000} value={form.details} onChange={set("details")} />
          </Field>
          {/* Honeypot: hidden from people, tempting to bots. */}
          <div style={{ position: "absolute", left: "-10000px" }} aria-hidden="true">
            <label>
              Website
              <input tabIndex={-1} autoComplete="off" value={form.website} onChange={set("website")} />
            </label>
          </div>
          {error && (
            <p role="alert" style={{ color: "var(--sf-brick)", fontSize: 13, marginBottom: 8 }}>
              {error}
            </p>
          )}
          <Button type="submit" disabled={busy}>
            {busy ? "Sending…" : "Send request"}
          </Button>
        </form>
      )}
    </LegalLayout>
  );
}
