import { useEffect, useId, useMemo, useRef, useState } from "react";

export interface ComboboxOption {
  id: string;
  label: string;
  sublabel?: string;
  disabled?: boolean;
}

/** Real, reusable, accessible combobox -- the shared foundation every
 * specific entity picker (VendorSelect, EmployeeSelect, etc.) builds
 * on, rather than each duplicating its own search/keyboard-nav/a11y
 * logic. Filters client-side over an already-fetched option list
 * (the caller's own job to fetch, matching every specific picker's
 * real, tenant-scoped list endpoint) -- appropriate for the
 * realistic size of a single tenant's vendors/employees/contracts/
 * equipment (tens to low hundreds, not thousands); a picker for a
 * genuinely large, unbounded list would need real server-side search
 * instead, not this component.
 *
 * Real ARIA combobox pattern (role="combobox", aria-expanded,
 * aria-activedescendant, aria-controls, listbox role on the popup) --
 * not a plain <select> pretending to be searchable. */
export function Combobox({
  id,
  value,
  onChange,
  options,
  placeholder = "Search…",
  loading = false,
  error = false,
  errorMessage = "Could not load options",
  emptyMessage = "No matches",
  disabled = false,
  required = false,
  clearable = true,
  "aria-label": ariaLabel,
}: {
  id?: string;
  value: string;
  onChange: (id: string) => void;
  options: ComboboxOption[] | null;
  placeholder?: string;
  loading?: boolean;
  error?: boolean;
  errorMessage?: string;
  emptyMessage?: string;
  disabled?: boolean;
  required?: boolean;
  clearable?: boolean;
  "aria-label"?: string;
}) {
  const generatedId = useId();
  const comboboxId = id ?? generatedId;
  const listboxId = `${comboboxId}-listbox`;

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedOption = options?.find((o) => o.id === value) ?? null;

  // Real, client-side filter -- matches label or sublabel, case-
  // insensitive substring, not just a prefix match, since a person
  // searching "Konga" for a vendor named "Konga Construction Ltd"
  // shouldn't need to type from the very start of the name.
  const filteredOptions = useMemo(() => {
    if (!options) return [];
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q) || o.sublabel?.toLowerCase().includes(q));
  }, [options, query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
        setActiveIndex(-1);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function selectOption(option: ComboboxOption) {
    if (option.disabled) return;
    onChange(option.id);
    setOpen(false);
    setQuery("");
    setActiveIndex(-1);
    inputRef.current?.blur();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (disabled) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setActiveIndex((i) => Math.min(i + 1, filteredOptions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (open && activeIndex >= 0 && filteredOptions[activeIndex]) {
        selectOption(filteredOptions[activeIndex]);
      } else {
        setOpen(true);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
      setActiveIndex(-1);
    } else if (e.key === "Backspace" && !query && value) {
      // Real, deliberate: backspacing on an empty search field over a
      // real selection clears it -- matches how a person expects to
      // "type over" whatever's currently chosen.
      onChange("");
    }
  }

  const displayValue = open ? query : selectedOption?.label ?? "";

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          border: "1px solid var(--sf-line)",
          borderRadius: "var(--sf-radius)",
          background: disabled ? "var(--sf-paper-dim)" : "#fff",
        }}
      >
        <input
          ref={inputRef}
          id={comboboxId}
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-activedescendant={activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined}
          aria-autocomplete="list"
          aria-label={ariaLabel}
          aria-required={required}
          autoComplete="off"
          disabled={disabled || loading}
          value={displayValue}
          placeholder={loading ? "Loading…" : error ? errorMessage : placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            padding: "8px 10px",
            fontSize: 13,
            fontFamily: "inherit",
            color: error ? "var(--sf-brick)" : "inherit",
          }}
        />
        {clearable && value && !disabled && (
          <button
            type="button"
            aria-label="Clear selection"
            onClick={() => {
              onChange("");
              setQuery("");
              inputRef.current?.focus();
            }}
            style={{ background: "none", border: "none", cursor: "pointer", padding: "0 10px", color: "var(--sf-navy-400)", fontSize: 14 }}
          >
            ×
          </button>
        )}
      </div>

      {open && !disabled && (
        <ul
          id={listboxId}
          role="listbox"
          style={{
            position: "absolute",
            zIndex: 20,
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            maxHeight: 240,
            overflowY: "auto",
            margin: 0,
            padding: 4,
            listStyle: "none",
            background: "#fff",
            border: "1px solid var(--sf-line)",
            borderRadius: "var(--sf-radius)",
            boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
          }}
        >
          {loading ? (
            <li style={{ padding: "8px 10px", fontSize: 13, color: "var(--sf-navy-400)" }}>Loading…</li>
          ) : error ? (
            <li style={{ padding: "8px 10px", fontSize: 13, color: "var(--sf-brick)" }}>{errorMessage}</li>
          ) : filteredOptions.length === 0 ? (
            <li style={{ padding: "8px 10px", fontSize: 13, color: "var(--sf-navy-400)" }}>{emptyMessage}</li>
          ) : (
            filteredOptions.map((option, i) => (
              <li
                key={option.id}
                id={`${listboxId}-option-${i}`}
                role="option"
                aria-selected={option.id === value}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectOption(option);
                }}
                onMouseEnter={() => setActiveIndex(i)}
                style={{
                  padding: "8px 10px",
                  borderRadius: 4,
                  fontSize: 13,
                  cursor: option.disabled ? "not-allowed" : "pointer",
                  opacity: option.disabled ? 0.5 : 1,
                  background: i === activeIndex ? "var(--sf-paper-dim)" : "transparent",
                  color: option.id === value ? "var(--sf-steel)" : "inherit",
                  fontWeight: option.id === value ? 600 : 400,
                }}
              >
                <div>{option.label}</div>
                {option.sublabel && (
                  <div style={{ fontSize: 11, color: "var(--sf-navy-400)" }}>{option.sublabel}</div>
                )}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
