import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { UseQueryResult } from "@tanstack/react-query";
import { QueryState } from "./QueryState";

function makeQuery(overrides: Partial<UseQueryResult<any>>): UseQueryResult<any> {
  return {
    isLoading: false,
    isError: false,
    data: undefined,
    error: null as unknown as Error,
    refetch: vi.fn(),
    ...overrides,
  } as UseQueryResult<any>;
}

describe("QueryState", () => {
  it("shows a loading state while the query is loading", () => {
    render(<QueryState query={makeQuery({ isLoading: true })}>{() => <div>data</div>}</QueryState>);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("data")).not.toBeInTheDocument();
  });

  it("shows a retryable error state and calls refetch", async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    const err = { isAxiosError: true, response: { status: 500, data: {} } };
    render(
      <QueryState query={makeQuery({ isError: true, error: err as unknown as Error, refetch })}>{() => <div>data</div>}</QueryState>
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(refetch).toHaveBeenCalled();
  });

  it("does not show a retry button for a 403", () => {
    const err = { isAxiosError: true, response: { status: 403, data: {} } };
    render(<QueryState query={makeQuery({ isError: true, error: err as unknown as Error })}>{() => <div>data</div>}</QueryState>);
    expect(screen.getByText(/don't have permission/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("shows the empty state for an empty array", () => {
    render(
      <QueryState query={makeQuery({ data: [] })} emptyTitle="No items">
        {() => <div>data</div>}
      </QueryState>
    );
    expect(screen.getByText("No items")).toBeInTheDocument();
  });

  it("renders children with the data once loaded", () => {
    render(<QueryState query={makeQuery({ data: [1, 2] })}>{(data) => <div>{data.length} items</div>}</QueryState>);
    expect(screen.getByText("2 items")).toBeInTheDocument();
  });
});
