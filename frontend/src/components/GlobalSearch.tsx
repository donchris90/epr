import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../api/client";

interface SearchResult {
  type: string;
  id: string;
  label: string;
  status: string | null;
  url: string;
}

const TYPE_LABELS: Record<string, string> = {
  project: "Project",
  client: "Client",
  vendor: "Vendor",
  contract: "Contract",
  employee: "Employee",
  document: "Document",
  purchase_order: "Purchase Order",
};

// Real, fixed display order -- groups render in this sequence
// regardless of what order the backend happened to return them in.
const TYPE_ORDER = ["project", "contract", "client", "vendor", "purchase_order", "employee", "document"];

const RECENT_SEARCHES_KEY = "sf_recent_searches";
const MAX_RECENT_SEARCHES = 5;

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Search failed.";
}

/** Real, client-side recent-search history -- there's no backend
 * endpoint for this (a person's own recent searches on their own
 * browser is inherently a local UX concern, not something that needs
 * server persistence), stored per-browser via localStorage. */
function loadRecentSearches(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_SEARCHES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveRecentSearch(query: string) {
  const existing = loadRecentSearches().filter((q) => q.toLowerCase() !== query.toLowerCase());
  const next = [query, ...existing].slice(0, MAX_RECENT_SEARCHES);
  try {
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(next));
  } catch {
    // Real, deliberate: a full/unavailable localStorage (private
    // browsing, quota) shouldn't break search itself -- recent
    // searches are a convenience, not a requirement.
  }
}

/** Real global search -- backed by GET /v1/search
 * (app/search/services.py), itself RBAC-gated per entity type
 * server-side across Projects, Contracts, Clients, Vendors, Purchase
 * Orders, Employees, and Documents. This component doesn't duplicate
 * any of that logic; it just displays whatever the backend actually
 * decided the caller can see -- grouped, filterable, and keyboard-
 * navigable, but never expanding what's visible beyond the real,
 * already-scoped result set. */
export function GlobalSearch({ variant = "inline" }: { variant?: "inline" | "icon" }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(variant === "inline");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTypeFilter, setActiveTypeFilter] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setRecentSearches(loadRecentSearches());
  }, []);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults(null);
      setError(null);
      return;
    }
    const timeout = setTimeout(async () => {
      try {
        const res = await apiClient.get("/search", { params: { q: query.trim() } });
        setResults(res.data.data);
        setError(null);
        setActiveIndex(-1);
        saveRecentSearch(query.trim());
        setRecentSearches(loadRecentSearches());
      } catch (err: any) {
        setError(getErrorMessage(err));
        setResults(null);
      }
    }, 250);
    return () => clearTimeout(timeout);
  }, [query]);

  useEffect(() => {
    if (variant === "icon" && open) {
      inputRef.current?.focus();
    }
  }, [open, variant]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (variant === "icon" && containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
        setResults(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [variant]);

  const availableTypes = useMemo(() => {
    if (!results) return [];
    const present = new Set(results.map((r) => r.type));
    return TYPE_ORDER.filter((t) => present.has(t));
  }, [results]);

  const filteredResults = useMemo(() => {
    if (!results) return [];
    return activeTypeFilter ? results.filter((r) => r.type === activeTypeFilter) : results;
  }, [results, activeTypeFilter]);

  // Real, stable flat order matching what's actually rendered
  // (grouped by type, in TYPE_ORDER) -- keyboard navigation moves
  // through this same sequence, so arrow keys always land on the
  // visually next/previous result.
  const orderedResults = useMemo(() => {
    const byType = new Map<string, SearchResult[]>();
    for (const r of filteredResults) {
      if (!byType.has(r.type)) byType.set(r.type, []);
      byType.get(r.type)!.push(r);
    }
    return TYPE_ORDER.flatMap((t) => byType.get(t) ?? []);
  }, [filteredResults]);

  function handleSelect(result: SearchResult) {
    setQuery("");
    setResults(null);
    setActiveTypeFilter(null);
    if (variant === "icon") setOpen(false);
    navigate(result.url);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (orderedResults.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, orderedResults.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      handleSelect(orderedResults[activeIndex]);
    } else if (e.key === "Escape") {
      setResults(null);
      setQuery("");
    }
  }

  const showDropdown = query.trim().length >= 2 || (variant === "icon" && open && query.trim().length === 0 && recentSearches.length > 0);

  if (variant === "icon" && !open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Search"
        style={{
          background: "none",
          border: "1px solid var(--sf-navy-700)",
          borderRadius: "var(--sf-radius)",
          width: 34,
          height: 34,
          color: "var(--sf-navy-200)",
          cursor: "pointer",
          fontSize: 15,
        }}
      >
        🔍
      </button>
    );
  }

  return (
    <div ref={containerRef} style={{ position: "relative", width: variant === "inline" ? "100%" : 220 }}>
      <input
        ref={inputRef}
        role="combobox"
        aria-expanded={showDropdown}
        aria-label="Global search"
        autoComplete="off"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Search projects, contracts, clients, vendors…"
        style={{
          width: "100%",
          padding: "8px 12px",
          borderRadius: "var(--sf-radius)",
          border: variant === "inline" ? "1px solid var(--sf-navy-700)" : "1px solid var(--sf-line)",
          background: variant === "inline" ? "var(--sf-navy-900)" : "#fff",
          color: variant === "inline" ? "var(--sf-navy-200)" : "var(--sf-navy-900)",
          fontSize: 13,
          fontFamily: "inherit",
        }}
      />

      {showDropdown && (
        <div
          style={{
            position: "absolute",
            top: 40,
            left: 0,
            right: 0,
            maxHeight: 420,
            overflowY: "auto",
            background: "#fff",
            border: "1px solid var(--sf-line)",
            borderRadius: "var(--sf-radius)",
            boxShadow: "0 8px 24px rgba(33, 26, 20, 0.18)",
            zIndex: 60,
          }}
        >
          {query.trim().length < 2 ? (
            <div style={{ padding: 12 }}>
              <div style={{ fontSize: 11, color: "var(--sf-navy-400)", textTransform: "uppercase", padding: "2px 2px 8px" }}>
                Recent searches
              </div>
              {recentSearches.map((q) => (
                <div
                  key={q}
                  onClick={() => setQuery(q)}
                  style={{ padding: "8px 8px", fontSize: 13, color: "var(--sf-navy-700)", cursor: "pointer", borderRadius: 4 }}
                >
                  {q}
                </div>
              ))}
            </div>
          ) : error ? (
            <div style={{ padding: 14, fontSize: 13, color: "var(--sf-brick)" }}>{error}</div>
          ) : results === null ? (
            <div style={{ padding: 14, fontSize: 13, color: "var(--sf-navy-400)" }}>Searching…</div>
          ) : results.length === 0 ? (
            <div style={{ padding: 14, fontSize: 13, color: "var(--sf-navy-400)" }}>No matches for "{query}".</div>
          ) : (
            <>
              {availableTypes.length > 1 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, padding: "10px 14px 4px", borderBottom: "1px solid var(--sf-line)" }}>
                  <button
                    onClick={() => setActiveTypeFilter(null)}
                    aria-pressed={activeTypeFilter === null}
                    style={filterChipStyle(activeTypeFilter === null)}
                  >
                    All
                  </button>
                  {availableTypes.map((t) => (
                    <button
                      key={t}
                      onClick={() => setActiveTypeFilter(t)}
                      aria-pressed={activeTypeFilter === t}
                      style={filterChipStyle(activeTypeFilter === t)}
                    >
                      {TYPE_LABELS[t] ?? t}
                    </button>
                  ))}
                </div>
              )}

              {TYPE_ORDER.filter((t) => filteredResults.some((r) => r.type === t)).map((type) => (
                <div key={type}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--sf-navy-400)", textTransform: "uppercase", padding: "10px 14px 4px" }}>
                    {TYPE_LABELS[type] ?? type}
                  </div>
                  {filteredResults
                    .filter((r) => r.type === type)
                    .map((r) => {
                      const flatIndex = orderedResults.indexOf(r);
                      return (
                        <div
                          key={`${r.type}-${r.id}`}
                          onClick={() => handleSelect(r)}
                          onMouseEnter={() => setActiveIndex(flatIndex)}
                          style={{
                            padding: "10px 14px",
                            cursor: "pointer",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            background: flatIndex === activeIndex ? "var(--sf-paper-dim)" : "transparent",
                          }}
                        >
                          <span style={{ fontSize: 13, color: "var(--sf-navy-900)" }}>{r.label}</span>
                          {r.status && (
                            <span
                              className="sf-mono"
                              style={{ fontSize: 11, color: "var(--sf-steel)", background: "var(--sf-steel-dim)", borderRadius: 999, padding: "2px 8px" }}
                            >
                              {r.status}
                            </span>
                          )}
                        </div>
                      );
                    })}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function filterChipStyle(active: boolean): React.CSSProperties {
  return {
    fontSize: 11,
    padding: "3px 10px",
    borderRadius: 999,
    border: "1px solid " + (active ? "var(--sf-steel)" : "var(--sf-line)"),
    background: active ? "var(--sf-steel-dim)" : "#fff",
    color: active ? "var(--sf-steel)" : "var(--sf-navy-600)",
    cursor: "pointer",
  };
}
