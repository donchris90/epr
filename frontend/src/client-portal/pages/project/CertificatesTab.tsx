import { useParams } from "react-router-dom";
import { Table, Th, Td, Badge, formatMoney } from "../../../components/ui";
import { useClientCertificates, useDecideCertificate } from "../../hooks";
import { QueryState } from "../../components/QueryState";
import { DecisionActions } from "../../components/DecisionActions";

interface Certificate {
  id: string;
  certificate_number: string;
  period_start: string | null;
  period_end: string | null;
  gross_certified_amount: string;
  retention_withheld: string;
  net_payable: string;
  status: string;
}

function statusTone(status: string): "green" | "amber" | "brick" | "neutral" {
  if (status === "client_approved") return "green";
  if (status === "submitted") return "amber";
  if (status === "rejected") return "brick";
  return "neutral";
}

/** Certificates (item 8) + Approvals for certificates (part of item
 * 10): a certificate in status='submitted' is exactly the set
 * awaiting the client's decision -- CLP-05's own state machine, not
 * a frontend-invented status. */
export default function CertificatesTab() {
  const { projectId } = useParams<{ projectId: string }>();
  const certificates = useClientCertificates(projectId);
  const decide = useDecideCertificate();

  return (
    <QueryState query={certificates} emptyTitle="No certificates yet" emptyHint="Progress certificates submitted for this project will appear here.">
      {(data: Certificate[]) => (
        <Table>
          <thead>
            <tr>
              <Th>Certificate</Th>
              <Th>Period</Th>
              <Th>Gross certified</Th>
              <Th>Retention</Th>
              <Th>Net payable</Th>
              <Th>Status</Th>
              <Th></Th>
            </tr>
          </thead>
          <tbody>
            {data.map((c) => (
              <tr key={c.id}>
                <Td mono>{c.certificate_number}</Td>
                <Td mono>
                  {c.period_start ?? "—"} – {c.period_end ?? "—"}
                </Td>
                <Td>{formatMoney(c.gross_certified_amount)}</Td>
                <Td>{formatMoney(c.retention_withheld)}</Td>
                <Td>{formatMoney(c.net_payable)}</Td>
                <Td>
                  <Badge tone={statusTone(c.status)}>{c.status.replace(/_/g, " ")}</Badge>
                </Td>
                <Td>
                  {c.status === "submitted" && (
                    <DecisionActions
                      onDecide={(decision, notes) =>
                        decide.mutateAsync({ certificate_id: c.id, project_id: projectId!, decision, notes: notes || undefined }).then(() => {})
                      }
                    />
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </QueryState>
  );
}
