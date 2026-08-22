import { useParams } from "react-router-dom";
import { Table, Th, Td, Badge, formatMoney } from "../../../components/ui";
import { useClientVariationOrders, useDecideVariationOrder } from "../../hooks";
import { QueryState } from "../../components/QueryState";
import { DecisionActions } from "../../components/DecisionActions";

interface VariationOrder {
  id: string;
  description: string;
  varied_quantity: string;
  varied_rate: string;
  status: string;
}

function statusTone(status: string): "green" | "amber" | "brick" | "neutral" {
  if (status === "approved") return "green";
  if (status === "pending") return "amber";
  if (status === "rejected") return "brick";
  return "neutral";
}

/** Variations (item 9) + Approvals for variations (part of item 10):
 * a variation order in status='pending' is exactly the set awaiting
 * the client's decision -- BIL-04's own state machine. */
export default function VariationsTab() {
  const { projectId } = useParams<{ projectId: string }>();
  const variations = useClientVariationOrders(projectId);
  const decide = useDecideVariationOrder();

  return (
    <QueryState query={variations} emptyTitle="No variation orders yet" emptyHint="Variation orders raised against this project's contract will appear here.">
      {(data: VariationOrder[]) => (
        <Table>
          <thead>
            <tr>
              <Th>Description</Th>
              <Th>Varied qty</Th>
              <Th>Rate</Th>
              <Th>Status</Th>
              <Th></Th>
            </tr>
          </thead>
          <tbody>
            {data.map((v) => (
              <tr key={v.id}>
                <Td>{v.description}</Td>
                <Td mono>{v.varied_quantity}</Td>
                <Td>{formatMoney(v.varied_rate)}</Td>
                <Td>
                  <Badge tone={statusTone(v.status)}>{v.status}</Badge>
                </Td>
                <Td>
                  {v.status === "pending" && (
                    <DecisionActions
                      onDecide={(decision, notes) =>
                        decide.mutateAsync({ vo_id: v.id, project_id: projectId!, decision, notes: notes || undefined }).then(() => {})
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
