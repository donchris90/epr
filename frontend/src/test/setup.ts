import "@testing-library/jest-dom";

// jsdom doesn't implement ResizeObserver at all -- @xyflow/react (the
// visual workflow builder) needs it internally to measure the canvas
// on mount. A minimal, honest stub: tests don't need real resize
// observation, just for the API to exist so React Flow's own effect
// doesn't throw ReferenceError: ResizeObserver is not defined.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// @ts-expect-error -- intentionally global, matching how jsdom itself exposes browser APIs
global.ResizeObserver = ResizeObserverStub;
