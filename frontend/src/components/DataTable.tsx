import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Button, Input, Table, Th, Td, EmptyState } from "./ui";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Omit to make the column unsortable. */
  sortValue?: (row: T) => string | number | null | undefined;
  /** Omit to make the column always visible (can't be hidden via the column-visibility menu). */
  hideable?: boolean;
  align?: "left" | "right";
  /** Only for the sr-only per-column caption on truly numeric columns; visual alignment still comes from `align`. */
  numeric?: boolean;
  /** Plain-text value for this column, used only for CSV export -- `render` returns a
   * ReactNode, which can't be serialized to a cell string directly. Omit to fall back
   * to sortValue's own value, or an empty cell if neither is provided. */
  exportValue?: (row: T) => string | number | null | undefined;
}

export interface BulkAction<T> {
  label: string;
  onClick: (selected: T[]) => void;
  tone?: "secondary" | "danger";
}

/**
 * One reusable table for list pages: client-side search, sortable
 * columns (click a header), pagination, show/hide columns, per-row
 * actions, and an optional bulk-action toolbar that appears once
 * rows are checked. Sorting/pagination/search all run over the rows
 * already loaded by the page's own query -- there's no backend
 * pagination endpoint to page against yet, so this is the real,
 * useful thing to reuse today rather than a client/server-paginated
 * table with no server side to call.
 */
export function DataTable<T>({
  columns,
  rows,
  getRowId,
  searchPlaceholder = "Search…",
  searchFields,
  pageSize = 20,
  rowActions,
  bulkActions,
  emptyTitle = "No results",
  emptyHint,
  emptyAction,
  filters,
  exportFilename,
}: {
  columns: DataTableColumn<T>[];
  rows: T[];
  getRowId: (row: T) => string;
  searchPlaceholder?: string;
  /** Fields checked against the search box, stringified. Omit to disable the search box entirely. */
  searchFields?: (row: T) => (string | number | null | undefined)[];
  pageSize?: number;
  rowActions?: (row: T) => ReactNode;
  bulkActions?: BulkAction<T>[];
  emptyTitle?: string;
  emptyHint?: string;
  emptyAction?: ReactNode;
  /** Caller-supplied filter controls (Selects, date pickers, ...), rendered in the toolbar next to search. */
  filters?: ReactNode;
  /** Omit to disable CSV export entirely -- not every table needs it. When set, an
   * "Export CSV" button downloads the currently filtered/sorted rows (every column,
   * regardless of show/hide state, so the exported file is always complete) as
   * `${exportFilename}.csv`, generated client-side since there's no backend export
   * endpoint to call. */
  exportFilename?: string;
}) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [hiddenCols, setHiddenCols] = useState<Set<string>>(new Set());
  const [colMenuOpen, setColMenuOpen] = useState(false);

  const filtered = useMemo(() => {
    if (!search.trim() || !searchFields) return rows;
    const q = search.trim().toLowerCase();
    return rows.filter((r) => searchFields(r).some((v) => String(v ?? "").toLowerCase().includes(q)));
  }, [rows, search, searchFields]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return filtered;
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = col.sortValue!(a) ?? "";
      const bv = col.sortValue!(b) ?? "";
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [filtered, sortKey, sortDir, columns]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const clampedPage = Math.min(page, totalPages);
  const pageRows = sorted.slice((clampedPage - 1) * pageSize, clampedPage * pageSize);

  useEffect(() => {
    setPage(1);
  }, [search, rows.length]);

  const visibleColumns = columns.filter((c) => !hiddenCols.has(c.key));
  const selectedRows = rows.filter((r) => selected.has(getRowId(r)));
  const allOnPageSelected = pageRows.length > 0 && pageRows.every((r) => selected.has(getRowId(r)));

  function toggleSort(col: DataTableColumn<T>) {
    if (!col.sortValue) return;
    if (sortKey === col.key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(col.key);
      setSortDir("asc");
    }
  }

  function toggleRow(id: string) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAllOnPage() {
    setSelected((s) => {
      const next = new Set(s);
      if (allOnPageSelected) {
        pageRows.forEach((r) => next.delete(getRowId(r)));
      } else {
        pageRows.forEach((r) => next.add(getRowId(r)));
      }
      return next;
    });
  }

  function csvCell(value: string | number | null | undefined): string {
    const s = String(value ?? "");
    // Real RFC 4180 escaping -- a value containing a comma, quote, or
    // newline must be wrapped in quotes, with any internal quote
    // doubled. Without this, a name like `Smith, John` or a
    // description containing a literal quote would silently corrupt
    // the file's column structure when opened in a spreadsheet.
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }

  function handleExport() {
    const headerRow = columns.map((c) => csvCell(c.header)).join(",");
    const dataRows = sorted.map((row) =>
      columns.map((c) => csvCell((c.exportValue ?? c.sortValue)?.(row))).join(",")
    );
    const csv = [headerRow, ...dataRows].join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${exportFilename}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12, alignItems: "center" }}>
        {searchFields && (
          <div style={{ flex: "1 1 220px", maxWidth: 320 }}>
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
            />
          </div>
        )}
        {filters}
        {exportFilename && sorted.length > 0 && (
          <Button variant="secondary" onClick={handleExport}>
            Export CSV
          </Button>
        )}
        <div style={{ position: "relative", marginLeft: "auto" }}>
          <Button variant="secondary" onClick={() => setColMenuOpen((v) => !v)} aria-expanded={colMenuOpen} aria-haspopup="true">
            Columns
          </Button>
          {colMenuOpen && (
            <div
              role="menu"
              aria-label="Toggle column visibility"
              style={{
                position: "absolute",
                right: 0,
                top: "calc(100% + 4px)",
                background: "#fff",
                border: "1px solid var(--sf-line)",
                borderRadius: "var(--sf-radius)",
                boxShadow: "var(--sf-shadow)",
                padding: 10,
                zIndex: 10,
                minWidth: 180,
              }}
            >
              {columns
                .filter((c) => c.hideable !== false)
                .map((c) => (
                  <label key={c.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, padding: "4px 2px", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={!hiddenCols.has(c.key)}
                      onChange={() =>
                        setHiddenCols((s) => {
                          const next = new Set(s);
                          if (next.has(c.key)) next.delete(c.key);
                          else next.add(c.key);
                          return next;
                        })
                      }
                    />
                    {c.header}
                  </label>
                ))}
            </div>
          )}
        </div>
      </div>

      {bulkActions && selected.size > 0 && (
        <div
          role="toolbar"
          aria-label="Bulk actions"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "8px 12px",
            marginBottom: 8,
            background: "var(--sf-amber-dim)",
            borderRadius: "var(--sf-radius)",
            fontSize: 13,
          }}
        >
          <span style={{ fontWeight: 600 }}>{selected.size} selected</span>
          {bulkActions.map((a) => (
            <Button key={a.label} variant={a.tone === "danger" ? "danger" : "secondary"} onClick={() => a.onClick(selectedRows)}>
              {a.label}
            </Button>
          ))}
          <button
            onClick={() => setSelected(new Set())}
            style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--sf-navy-600)", cursor: "pointer", fontSize: 12 }}
          >
            Clear
          </button>
        </div>
      )}

      {sorted.length === 0 ? (
        <EmptyState title={emptyTitle} hint={emptyHint} action={emptyAction} />
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                {bulkActions && (
                  <Th>
                    <input
                      type="checkbox"
                      checked={allOnPageSelected}
                      onChange={toggleAllOnPage}
                      aria-label="Select all rows on this page"
                    />
                  </Th>
                )}
                {visibleColumns.map((c) => (
                  <Th key={c.key}>
                    {c.sortValue ? (
                      <button
                        onClick={() => toggleSort(c)}
                        aria-label={`Sort by ${c.header}${sortKey === c.key ? (sortDir === "asc" ? ", ascending" : ", descending") : ""}`}
                        style={{
                          background: "none",
                          border: "none",
                          padding: 0,
                          font: "inherit",
                          fontWeight: 700,
                          color: "inherit",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        {c.header}
                        <span aria-hidden="true" style={{ fontSize: 10, opacity: sortKey === c.key ? 1 : 0.3 }}>
                          {sortKey === c.key && sortDir === "desc" ? "▼" : "▲"}
                        </span>
                      </button>
                    ) : (
                      c.header
                    )}
                  </Th>
                ))}
                {rowActions && <Th />}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((row) => {
                const id = getRowId(row);
                return (
                  <tr key={id}>
                    {bulkActions && (
                      <Td>
                        <input type="checkbox" checked={selected.has(id)} onChange={() => toggleRow(id)} aria-label="Select row" />
                      </Td>
                    )}
                    {visibleColumns.map((c) => (
                      <Td key={c.key} style={c.align === "right" ? { textAlign: "right" } : undefined}>
                        {c.render(row)}
                      </Td>
                    ))}
                    {rowActions && <Td style={{ textAlign: "right" }}>{rowActions(row)}</Td>}
                  </tr>
                );
              })}
            </tbody>
          </Table>

          {totalPages > 1 && (
            <nav
              aria-label="Table pagination"
              style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 4px", fontSize: 13 }}
            >
              <span style={{ color: "var(--sf-navy-400)" }}>
                Page {clampedPage} of {totalPages} &middot; {sorted.length} results
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <Button variant="secondary" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={clampedPage <= 1}>
                  Previous
                </Button>
                <Button variant="secondary" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={clampedPage >= totalPages}>
                  Next
                </Button>
              </div>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
