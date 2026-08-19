import { useEffect, useRef, useState } from "react";
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
};

function getErrorMessage(err: any): string {
  return err?.response?.data?.detail || err?.response?.data?.title || "Search failed.";
}

/** Real global search -- backed by GET /v1/search (built earlier this
 * session), which is itself RBAC-gated per entity type server-side.
 * This component doesn't duplicate any of that logic; it just
 * displays whatever the backend actually decided the caller can see. */
export function GlobalSearch({ variant = "inline" }: { variant?: "inline" | "icon" }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(variant === "inline");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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

  function handleSelect(result: SearchResult) {
    setQuery("");
    setResults(null);
    if (variant === "icon") setOpen(false);
    navigate(result.url);
  }

  const showDropdown = query.trim().length >= 2;

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
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search projects, clients, vendors, contracts…"
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
            maxHeight: 360,
            overflowY: "auto",
            background: "#fff",
            border: "1px solid var(--sf-line)",
            borderRadius: "var(--sf-radius)",
            boxShadow: "0 8px 24px rgba(33, 26, 20, 0.18)",
            zIndex: 60,
          }}
        >
          {error ? (
            <div style={{ padding: 14, fontSize: 13, color: "var(--sf-brick)" }}>{error}</div>
          ) : results === null ? (
            <div style={{ padding: 14, fontSize: 13, color: "var(--sf-navy-400)" }}>Searching…</div>
          ) : results.length === 0 ? (
            <div style={{ padding: 14, fontSize: 13, color: "var(--sf-navy-400)" }}>No matches for "{query}".</div>
          ) : (
            results.map((r) => (
              <div
                key={`${r.type}-${r.id}`}
                onClick={() => handleSelect(r)}
                style={{
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--sf-line)",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span style={{ fontSize: 13, color: "var(--sf-navy-900)" }}>{r.label}</span>
                <span
                  className="sf-mono"
                  style={{ fontSize: 11, color: "var(--sf-steel)", background: "var(--sf-steel-dim)", borderRadius: 999, padding: "2px 8px" }}
                >
                  {TYPE_LABELS[r.type] ?? r.type}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
