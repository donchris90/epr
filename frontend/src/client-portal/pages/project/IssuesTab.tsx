import { useState } from "react";
import { useParams } from "react-router-dom";
import { Card, Badge, Button, Select, Textarea } from "../../../components/ui";
import { useClientRequests, useSubmitClientRequest } from "../../hooks";
import { QueryState } from "../../components/QueryState";

interface ClientRequestRow {
  id: string;
  request_type: "rfi" | "service_request";
  description: string;
  status: "open" | "in_progress" | "resolved";
  response: string | null;
  submitted_at: string;
  resolved_at: string | null;
}

function statusTone(status: string): "green" | "amber" | "neutral" {
  if (status === "resolved") return "green";
  if (status === "in_progress") return "amber";
  return "neutral";
}

/** Issues (item 13) + Messages/communication (item 14, "where
 * supported"): both map to the same ClientRequest entity (CLP-07) --
 * there is no dedicated issue tracker or messaging thread a client
 * can safely see anywhere else in this codebase (NCR/punch-list rows
 * in Module 15 are internal QA artifacts with no client-scoping proxy
 * at all). Each request IS a two-message thread: the client's
 * description, and staff's eventual response. See
 * docs/CLIENT_PORTAL_GAPS.md for what real messaging would need. */
export default function IssuesTab() {
  const { projectId } = useParams<{ projectId: string }>();
  const requests = useClientRequests(projectId);
  const submit = useSubmitClientRequest();

  const [requestType, setRequestType] = useState<"rfi" | "service_request">("rfi");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await submit.mutateAsync({ project_id: projectId!, request_type: requestType, description });
      setDescription("");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.response?.data?.title || "Could not submit your request.");
    }
  }

  return (
    <div>
      <Card style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, marginBottom: 10 }}>Raise an issue or ask a question</h3>
        <form onSubmit={handleSubmit}>
          <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
            <Select
              value={requestType}
              onChange={(e) => setRequestType(e.target.value === "service_request" ? "service_request" : "rfi")}
              style={{ maxWidth: 200 }}
            >
              <option value="rfi">Request for information</option>
              <option value="service_request">Service request</option>
            </Select>
          </div>
          <Textarea
            required
            placeholder="Describe your question or issue…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            style={{ marginBottom: 10 }}
          />
          {error && <div style={{ color: "var(--sf-brick)", fontSize: 12, marginBottom: 10 }}>{error}</div>}
          <Button type="submit" disabled={submit.isPending}>
            {submit.isPending ? "Sending…" : "Send"}
          </Button>
        </form>
      </Card>

      <h3 style={{ fontSize: 14, marginBottom: 10 }}>Your requests</h3>
      <QueryState query={requests} emptyTitle="No requests yet" emptyHint="Issues and questions you send will appear here, along with your project team's response.">
        {(data: ClientRequestRow[]) => (
          <div style={{ display: "grid", gap: 12 }}>
            {data.map((r) => (
              <Card key={r.id}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <Badge tone="steel">{r.request_type === "rfi" ? "RFI" : "Service request"}</Badge>
                  <Badge tone={statusTone(r.status)}>{r.status.replace(/_/g, " ")}</Badge>
                </div>
                <div style={{ fontSize: 13, marginBottom: 4 }}>{r.description}</div>
                <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginBottom: r.response ? 10 : 0 }}>
                  You — {new Date(r.submitted_at).toLocaleString()}
                </div>
                {r.response && (
                  <div style={{ borderTop: "1px solid var(--sf-line)", paddingTop: 10 }}>
                    <div style={{ fontSize: 13 }}>{r.response}</div>
                    <div style={{ fontSize: 11, color: "var(--sf-navy-400)", marginTop: 4 }}>
                      Project team{r.resolved_at ? ` — ${new Date(r.resolved_at).toLocaleString()}` : ""}
                    </div>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </QueryState>
    </div>
  );
}
