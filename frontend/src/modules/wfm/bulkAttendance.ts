import type { BulkAttendanceRow } from "./hooks";

export type Mark = "" | "present" | "absent";

export interface CrewEntry {
  key: string; // "e:<id>" | "c:<id>"
  kind: "employee" | "casual";
  id: string;
  name: string;
  mark: Mark;
  timeIn: string; // "HH:MM"
  timeOut: string;
}

/** Builds the API rows from the sheet: unmarked people are left out,
 * "absent" is a row with no times, "present" carries the typed times
 * (date + HH:MM, no zone -- same format the Correct action sends). */
export function buildBulkRows(entries: CrewEntry[], date: string): BulkAttendanceRow[] {
  return entries
    .filter((e) => e.mark !== "")
    .map((e) => {
      const row: BulkAttendanceRow = e.kind === "employee" ? { employee_id: e.id } : { casual_worker_id: e.id };
      if (e.mark === "present") {
        row.check_in_at = e.timeIn ? `${date}T${e.timeIn}:00` : null;
        row.check_out_at = e.timeIn && e.timeOut ? `${date}T${e.timeOut}:00` : null;
      }
      return row;
    });
}

/** Returns a message for the first problem, or null. */
export function validateEntries(entries: CrewEntry[]): string | null {
  for (const e of entries) {
    if (e.mark === "present" && e.timeIn && e.timeOut && e.timeOut <= e.timeIn) {
      return `${e.name}: finish time must be after start time.`;
    }
  }
  if (!entries.some((e) => e.mark !== "")) return "Mark at least one person present or absent.";
  return null;
}
