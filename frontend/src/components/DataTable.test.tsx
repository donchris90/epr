import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTable } from "./DataTable";

interface Row {
  id: string;
  name: string;
  amount: number;
}

const ROWS: Row[] = [
  { id: "a", name: "Bravo", amount: 30 },
  { id: "b", name: "Alpha", amount: 10 },
  { id: "c", name: "Charlie", amount: 20 },
];

const columns = [
  { key: "name", header: "Name", render: (r: Row) => r.name, sortValue: (r: Row) => r.name },
  { key: "amount", header: "Amount", render: (r: Row) => String(r.amount), sortValue: (r: Row) => r.amount, align: "right" as const },
];

describe("DataTable", () => {
  it("renders all rows by default", () => {
    render(<DataTable columns={columns} rows={ROWS} getRowId={(r) => r.id} />);
    expect(screen.getByText("Bravo")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Charlie")).toBeInTheDocument();
  });

  it("shows the empty state when there are no rows", () => {
    render(<DataTable columns={columns} rows={[]} getRowId={(r) => r.id} emptyTitle="No rows here" />);
    expect(screen.getByText("No rows here")).toBeInTheDocument();
  });

  it("filters rows via the search box", async () => {
    const user = userEvent.setup();
    render(
      <DataTable columns={columns} rows={ROWS} getRowId={(r) => r.id} searchFields={(r) => [r.name]} searchPlaceholder="Search rows…" />
    );
    await user.type(screen.getByPlaceholderText("Search rows…"), "alph");
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.queryByText("Bravo")).not.toBeInTheDocument();
  });

  it("sorts rows when a sortable header is clicked", async () => {
    const user = userEvent.setup();
    render(<DataTable columns={columns} rows={ROWS} getRowId={(r) => r.id} />);
    await user.click(screen.getByRole("button", { name: /sort by name/i }));
    const cells = screen.getAllByRole("row").slice(1); // drop header row
    expect(within(cells[0]).getByText("Alpha")).toBeInTheDocument();
  });

  it("paginates when there are more rows than the page size", () => {
    const manyRows = Array.from({ length: 25 }, (_, i) => ({ id: String(i), name: `Row ${i}`, amount: i }));
    render(<DataTable columns={columns} rows={manyRows} getRowId={(r) => r.id} pageSize={20} />);
    expect(screen.getByText(/page 1 of 2/i)).toBeInTheDocument();
    expect(screen.queryByText("Row 21")).not.toBeInTheDocument();
  });

  it("supports bulk selection and a bulk action", async () => {
    const user = userEvent.setup();
    const onBulk = vi.fn();
    render(
      <DataTable
        columns={columns}
        rows={ROWS}
        getRowId={(r) => r.id}
        bulkActions={[{ label: "Archive", onClick: onBulk }]}
      />
    );
    const checkboxes = screen.getAllByRole("checkbox", { name: /select row/i });
    await user.click(checkboxes[0]);
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Archive" }));
    expect(onBulk).toHaveBeenCalledWith([ROWS[0]]);
  });

  it("toggles column visibility", async () => {
    const user = userEvent.setup();
    render(<DataTable columns={columns} rows={ROWS} getRowId={(r) => r.id} />);
    await user.click(screen.getByRole("button", { name: "Columns" }));
    await user.click(screen.getByRole("checkbox", { name: "Amount" }));
    expect(screen.queryByRole("button", { name: /sort by amount/i })).not.toBeInTheDocument();
  });
});
