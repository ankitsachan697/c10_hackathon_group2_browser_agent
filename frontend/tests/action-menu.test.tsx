import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ActionMenu } from "@/components/ui/ActionMenu";

test("actions escape the table clipping boundary and do not activate the row", () => {
  const openRow = vi.fn();
  render(<div className="table-wrap" onClick={openRow}><ActionMenu label="Project actions">
    <button role="menuitem">Run now</button><button role="menuitem">Delete</button>
  </ActionMenu></div>);
  fireEvent.click(screen.getByRole("button", { name: "Project actions" }));
  const menu = screen.getByRole("menu");
  expect(menu.closest(".table-wrap")).toBeNull();
  expect(within(menu).getByRole("menuitem", { name: "Delete" })).toBeVisible();
  fireEvent.click(within(menu).getByRole("menuitem", { name: "Run now" }));
  expect(openRow).not.toHaveBeenCalled();
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
});

test("Escape dismisses actions and returns focus to their trigger", () => {
  render(<ActionMenu label="Project actions"><button role="menuitem">Run now</button></ActionMenu>);
  const trigger = screen.getByRole("button", { name: "Project actions" });
  fireEvent.click(trigger);
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

test("table scrolling keeps the actions open while their anchor moves", () => {
  const { container } = render(<div className="table-wrap"><ActionMenu label="Project actions"><button role="menuitem">Run now</button></ActionMenu></div>);
  fireEvent.click(screen.getByRole("button", { name: "Project actions" }));
  fireEvent.scroll(container.querySelector(".table-wrap")!);
  expect(screen.getByRole("menu")).toBeVisible();
});
