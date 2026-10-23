import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as api from "./api";

vi.mock("./api");

describe("App", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.listTodos.mockResolvedValue([]);
  });

  it("shows the empty state", async () => {
    render(<App />);
    expect(await screen.findByText(/nothing yet/i)).toBeInTheDocument();
  });

  it("lists todos from the API", async () => {
    api.listTodos.mockResolvedValue([
      { id: 1, title: "learn eks", done: false },
      { id: 2, title: "deploy", done: true },
    ]);
    render(<App />);
    expect(await screen.findByText("learn eks")).toBeInTheDocument();
    expect(screen.getByLabelText("deploy")).toBeChecked();
  });

  it("creates a todo and refreshes the list", async () => {
    api.createTodo.mockResolvedValue({ id: 1, title: "new", done: false });
    api.listTodos
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ id: 1, title: "new", done: false }]);
    render(<App />);
    await screen.findByText(/nothing yet/i);

    await userEvent.type(screen.getByLabelText("New todo"), "new");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(api.createTodo).toHaveBeenCalledWith("new");
    expect(await screen.findByText("new")).toBeInTheDocument();
  });

  it("toggles a todo", async () => {
    const todo = { id: 1, title: "a", done: false };
    api.listTodos.mockResolvedValue([todo]);
    api.updateTodo.mockResolvedValue({ ...todo, done: true });
    render(<App />);

    await userEvent.click(await screen.findByLabelText("a"));
    expect(api.updateTodo).toHaveBeenCalledWith({ ...todo, done: true });
  });

  it("deletes a todo", async () => {
    api.listTodos.mockResolvedValue([{ id: 7, title: "bye", done: false }]);
    api.deleteTodo.mockResolvedValue(null);
    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Delete bye" }));
    expect(api.deleteTodo).toHaveBeenCalledWith(7);
  });

  it("shows an error when the API fails", async () => {
    api.listTodos.mockRejectedValue(new Error("Request failed: 500"));
    render(<App />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("500"));
  });
});
