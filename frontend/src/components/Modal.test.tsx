import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Modal } from "./Modal";

describe("Modal", () => {
  it("renders with dialog semantics labelled by its title", () => {
    render(
      <Modal title="Create Project" onClose={() => {}}>
        <p>content</p>
      </Modal>
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName("Create Project");
  });

  it("calls onClose on Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <Modal title="Create Project" onClose={onClose}>
        <input placeholder="name" />
      </Modal>
    );
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("confirms before closing when confirmCloseIfDirty is set and the user cancels", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(
      <Modal title="Edit" onClose={onClose} confirmCloseIfDirty>
        <input placeholder="name" />
      </Modal>
    );
    await user.keyboard("{Escape}");
    expect(window.confirm).toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("moves focus into the dialog on open", () => {
    render(
      <Modal title="Create Project" onClose={() => {}}>
        <input placeholder="name" />
      </Modal>
    );
    expect(screen.getByPlaceholderText("name")).toHaveFocus();
  });
});
