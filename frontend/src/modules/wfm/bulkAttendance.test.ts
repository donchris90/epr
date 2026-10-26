import { describe, it, expect } from "vitest";
import { buildBulkRows, validateEntries, type CrewEntry } from "./bulkAttendance";

const E = (o: Partial<CrewEntry>): CrewEntry => ({ key: "e:1", kind: "employee", id: "1", name: "Ada", mark: "", timeIn: "07:00", timeOut: "16:00", ...o });

describe("buildBulkRows", () => {
  it("skips unmarked people, sends absences without times and presence with times", () => {
    const rows = buildBulkRows(
      [E({}), E({ id: "2", mark: "absent" }), E({ id: "3", kind: "casual", mark: "present" })],
      "2026-10-26"
    );
    expect(rows).toEqual([
      { employee_id: "2" },
      { casual_worker_id: "3", check_in_at: "2026-10-26T07:00:00", check_out_at: "2026-10-26T16:00:00" },
    ]);
  });

  it("omits check-out when there is no start, and allows start without finish", () => {
    expect(buildBulkRows([E({ mark: "present", timeIn: "", timeOut: "16:00" })], "2026-10-26")).toEqual([
      { employee_id: "1", check_in_at: null, check_out_at: null },
    ]);
    expect(buildBulkRows([E({ mark: "present", timeOut: "" })], "2026-10-26")).toEqual([
      { employee_id: "1", check_in_at: "2026-10-26T07:00:00", check_out_at: null },
    ]);
  });
});

describe("validateEntries", () => {
  it("needs at least one mark", () => {
    expect(validateEntries([E({})])).toMatch(/at least one/);
  });
  it("rejects finish before start, naming the person", () => {
    expect(validateEntries([E({ mark: "present", timeIn: "16:00", timeOut: "07:00" })])).toMatch(/Ada.*after start/);
  });
  it("accepts a valid sheet", () => {
    expect(validateEntries([E({ mark: "present" })])).toBeNull();
  });
});
