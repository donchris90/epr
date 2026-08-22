import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

type ToastTone = "success" | "error" | "info";

interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TONE_STYLE: Record<ToastTone, { bg: string; fg: string; border: string }> = {
  success: { bg: "var(--sf-green-dim)", fg: "var(--sf-green)", border: "var(--sf-green)" },
  error: { bg: "var(--sf-brick-dim)", fg: "var(--sf-brick)", border: "var(--sf-brick)" },
  info: { bg: "var(--sf-steel-dim)", fg: "var(--sf-steel)", border: "var(--sf-steel)" },
};

const AUTO_DISMISS_MS = 5000;

/** App-wide toast notifications -- mounted once in each shell
 * (AppShell, ClientPortalShell, platform admin shell) via
 * <ToastProvider>, called anywhere below it with useToast(). Used
 * for the "success notification" half of form UX (server validation
 * errors surface inline on the field instead -- see Field's `error`
 * prop -- since a toast that's already gone by the time someone
 * looks back at the form isn't useful for fixing input). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (tone: ToastTone, message: string) => {
      const id = ++idRef.current;
      setToasts((t) => [...t, { id, tone, message }]);
      window.setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss]
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => push("success", message),
      error: (message) => push("error", message),
      info: (message) => push("info", message),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        style={{
          position: "fixed",
          bottom: 20,
          right: 20,
          zIndex: 200,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          maxWidth: "min(360px, calc(100vw - 32px))",
        }}
      >
        {toasts.map((t) => {
          const tone = TONE_STYLE[t.tone];
          return (
            <div
              key={t.id}
              style={{
                background: tone.bg,
                color: tone.fg,
                border: `1px solid ${tone.border}`,
                borderRadius: "var(--sf-radius)",
                padding: "10px 14px",
                fontSize: 13,
                fontWeight: 500,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 12,
                boxShadow: "var(--sf-shadow)",
              }}
            >
              <span>{t.message}</span>
              <button
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                style={{ background: "none", border: "none", color: tone.fg, cursor: "pointer", fontSize: 14, lineHeight: 1, flexShrink: 0 }}
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Fails soft rather than throwing -- a page rendered in isolation
    // (e.g. a unit test that doesn't wrap ToastProvider) shouldn't
    // crash just because it never triggers a toast.
    return { success: () => {}, error: () => {}, info: () => {} };
  }
  return ctx;
}
