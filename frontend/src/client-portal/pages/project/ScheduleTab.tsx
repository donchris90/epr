import { useParams } from "react-router-dom";
import { Table, Th, Td, Badge } from "../../../components/ui";
import { useClientSchedule } from "../../hooks";
import { QueryState } from "../../components/QueryState";

interface Activity {
  activity_id: string;
  name: string;
  planned_start: string | null;
  early_start: string | null;
  early_finish: string | null;
  is_critical: boolean;
  percent_complete: string | null;
}

/** Schedule/status (item 5): the same read-only, cost-free activity
 * view CLP-06 already exposed -- this tab is the first real frontend
 * consumer of it. Critical-path activities are flagged, same meaning
 * as the internal planning module's own critical-path flag. */
export default function ScheduleTab() {
  const { projectId } = useParams<{ projectId: string }>();
  const schedule = useClientSchedule(projectId);

  return (
    <QueryState query={schedule} emptyTitle="No schedule published yet" emptyHint="Activities will appear here once your project's schedule is set up.">
      {(activities: Activity[]) => (
        <Table>
          <thead>
            <tr>
              <Th>Activity</Th>
              <Th>Planned start</Th>
              <Th>Early start</Th>
              <Th>Early finish</Th>
              <Th>% complete</Th>
              <Th>Critical path</Th>
            </tr>
          </thead>
          <tbody>
            {activities.map((a) => (
              <tr key={a.activity_id}>
                <Td>{a.name}</Td>
                <Td mono>{a.planned_start ?? "—"}</Td>
                <Td mono>{a.early_start ?? "—"}</Td>
                <Td mono>{a.early_finish ?? "—"}</Td>
                <Td mono>{a.percent_complete != null ? `${a.percent_complete}%` : "—"}</Td>
                <Td>{a.is_critical && <Badge tone="brick">Critical</Badge>}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </QueryState>
  );
}
