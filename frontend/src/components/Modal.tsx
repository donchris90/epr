import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { Card } from "./ui";

const FOCUSABLE = 'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/**
 * Shared accessible modal -- several pages had their own local
 * `Overlay` div (ProjectsPage, UsersManagementPage,
 * PlatformAdminTenantsPage, ...), each a plain positioned div with no
 * dialog semantics, no focus handling, and no Escape-to-close. This
 * consolidates that into one component with:
 *  - role="dialog" + aria-modal + aria-labelledby wired to `title`
 *  - focus moved into the dialog on open, returned to the trigger on close
 *  - Tab/Shift+Tab trapped within the dialog
 *  - Escape closes (unless `confirmCloseIfDirty` blocks it)
 *  - backdrop click closes (same guard)
 *
 * `confirmCloseIfDirty`: when true, closing via Escape or backdrop
 * asks for confirmation first -- the lightweight, non-router-coupled
 * way this app protects unsaved form state in a modal (see
 * lib/useUnsavedChanges.ts for the full-page/navigation equivalent).
 */
export function Modal({
  title,
  onClose,
  children,
  width = 440,
  confirmCloseIfDirty = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  width?: number;
  confirmCloseIfDirty?: boolean;
}) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<Element | null>(null);

  function requestClose() {
    if (confirmCloseIfDirty && !window.confirm("Discard unsaved changes?")) return;
    onClose();
  }

  useEffect(() => {
    triggerRef.current = document.activeElement;
    const dialog = dialogRef.current;
    const focusable = dialog?.querySelectorAll<HTMLElement>(FOCUSABLE);
    (focusable?.[0] ?? dialog)?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        requestClose();
        return;
      }
      if (e.key !== "Tab" || !dialog) return;
      const nodes = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((n) => n.offsetParent !== null);
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      (triggerRef.current as HTMLElement | null)?.focus?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      onClick={requestClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(33, 26, 20, 0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: 16,
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        style={{ width: "100%", maxWidth: width, maxHeight: "90vh", overflowY: "auto" }}
      >
        <Card>
          <div id={titleId} style={{ fontWeight: 700, fontSize: 16, marginBottom: 16 }}>
            {title}
          </div>
          {children}
        </Card>
      </div>
    </div>
  );
}
