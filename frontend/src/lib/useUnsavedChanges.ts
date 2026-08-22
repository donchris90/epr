import { useEffect } from "react";

/**
 * Warns before the tab/window closes or refreshes while `isDirty` is
 * true. Deliberately doesn't attempt to block in-app React Router
 * navigation: this app renders <BrowserRouter> (not a data router
 * via createBrowserRouter/RouterProvider), and react-router's
 * useBlocker requires a data router -- migrating the whole app to
 * one to get in-app nav blocking is a much bigger structural change
 * than this pass's scope. For the modal-based create/edit forms this
 * app actually uses, Modal's `confirmCloseIfDirty` prop covers the
 * equivalent in-app case (closing the modal itself).
 */
export function useUnsavedChanges(isDirty: boolean) {
  useEffect(() => {
    if (!isDirty) return;
    function handler(e: BeforeUnloadEvent) {
      e.preventDefault();
      e.returnValue = "";
    }
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);
}
