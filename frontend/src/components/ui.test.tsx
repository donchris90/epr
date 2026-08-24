import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "./ui";

describe("EmptyState", () => {
  it("renders the default, full variant with a title", () => {
    render(<EmptyState title="No purchase orders yet." />);
    expect(screen.getByText("No purchase orders yet.")).toBeInTheDocument();
  });

  it("renders the default variant's hint and action when provided", () => {
    render(<EmptyState title="No purchase orders yet." hint="Create your first one to get started." action={<button>Create</button>} />);
    expect(screen.getByText("Create your first one to get started.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeInTheDocument();
  });

  it("renders the real compact variant for in-card sub-sections", () => {
    render(<EmptyState compact title="No BOQ items imported yet." />);
    expect(screen.getByText("No BOQ items imported yet.")).toBeInTheDocument();
  });

  it("renders the compact variant's hint and action when provided", () => {
    render(<EmptyState compact title="No entries yet." hint="Add one to begin." action={<button>Add</button>} />);
    expect(screen.getByText("Add one to begin.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });
});
