import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { Button } from "./ui";

interface State {
  error: Error | null;
}

/** Catches render-time crashes (a bug in a page component, a null
 * dereference on unexpected data shape, etc) so one broken screen
 * shows a real recovery UI instead of a blank white page -- this is
 * the complement to the API-layer error handling in api/client.ts
 * and QueryState, which only cover request/response failures, not
 * exceptions thrown while rendering. */
export class RouteErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("Unhandled error rendering route:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ maxWidth: 480, margin: "80px auto", padding: "0 24px", textAlign: "center" }}>
          <div style={{ fontWeight: 700, fontSize: 18, color: "var(--sf-brick)", marginBottom: 8 }}>
            Something went wrong
          </div>
          <div style={{ fontSize: 13, color: "var(--sf-navy-600)", marginBottom: 20 }}>
            This page hit an unexpected error. Reloading usually fixes it; if it keeps happening, let us know what
            you were doing.
          </div>
          <Button onClick={() => window.location.reload()}>Reload page</Button>
        </div>
      );
    }
    return this.props.children;
  }
}
