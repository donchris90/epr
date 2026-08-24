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

  describe("CSV export", () => {
    function mockDownload() {
      const createObjectURL = vi.fn((_obj: Blob | MediaSource) => "blob:mock-url");
      const revokeObjectURL = vi.fn();
      vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
      const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
      return { createObjectURL, revokeObjectURL, clickSpy };
    }

    it("does not show an export button when exportFilename is omitted", () => {
      render(<DataTable columns={columns} rows={ROWS} getRowId={(r) => r.id} />);
      expect(screen.queryByRole("button", { name: /export csv/i })).not.toBeInTheDocument();
    });

    it("does not show an export button when there are no rows to export", () => {
      render(<DataTable columns={columns} rows={[]} getRowId={(r) => r.id} exportFilename="my-export" />);
      expect(screen.queryByRole("button", { name: /export csv/i })).not.toBeInTheDocument();
    });

    it("exports the real, currently visible rows as a correctly-formatted CSV, using exportValue over the raw render output", async () => {
      const { createObjectURL, clickSpy } = mockDownload();
      const user = userEvent.setup();
      const exportColumns = [
        { key: "name", header: "Name", render: (r: Row) => <strong>{r.name}</strong>, exportValue: (r: Row) => r.name },
        { key: "amount", header: "Amount", render: (r: Row) => `$${r.amount}`, exportValue: (r: Row) => r.amount },
      ];
      render(<DataTable columns={exportColumns} rows={ROWS} getRowId={(r) => r.id} exportFilename="my-report" />);

      await user.click(screen.getByRole("button", { name: /export csv/i }));

      expect(createObjectURL).toHaveBeenCalledTimes(1);
      const blob = createObjectURL.mock.calls[0][0] as Blob;
      const text = await blob.text();
      expect(text).toBe("Name,Amount\r\nBravo,30\r\nAlpha,10\r\nCharlie,20");
      expect(clickSpy).toHaveBeenCalledTimes(1);
    });

    it("downloads the real file using the given exportFilename", async () => {
      mockDownload();
      const user = userEvent.setup();
      const createElementSpy = vi.spyOn(document, "createElement");
      render(<DataTable columns={columns} rows={ROWS} getRowId={(r) => r.id} exportFilename="vendors-2026" />);

      await user.click(screen.getByRole("button", { name: /export csv/i }));

      const anchor = createElementSpy.mock.results.find((r) => r.value instanceof HTMLAnchorElement)?.value as HTMLAnchorElement;
      expect(anchor.download).toBe("vendors-2026.csv");
    });

    it("correctly escapes a real value containing a comma", async () => {
      const { createObjectURL } = mockDownload();
      const user = userEvent.setup();
      const commaRows = [{ id: "x", name: "Smith, John", amount: 5 }];
      render(<DataTable columns={columns} rows={commaRows} getRowId={(r) => r.id} exportFilename="test" />);

      await user.click(screen.getByRole("button", { name: /export csv/i }));

      const blob = createObjectURL.mock.calls[0][0] as Blob;
      const text = await blob.text();
      expect(text).toBe('Name,Amount\r\n"Smith, John",5');
    });

    it("only exports the real, currently filtered rows -- not every row", async () => {
      const { createObjectURL } = mockDownload();
      const user = userEvent.setup();
      render(
        <DataTable columns={columns} rows={ROWS} getRowId={(r) => r.id} searchFields={(r) => [r.name]} exportFilename="filtered" />
      );

      await user.type(screen.getByPlaceholderText("Search…"), "Alpha");
      await user.click(screen.getByRole("button", { name: /export csv/i }));

      const blob = createObjectURL.mock.calls[0][0] as Blob;
      const text = await blob.text();
      expect(text).toBe("Name,Amount\r\nAlpha,10");
    });
  });
});
