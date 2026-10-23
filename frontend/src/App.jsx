import { useEffect, useState } from "react";
import { createTodo, deleteTodo, listTodos, updateTodo } from "./api";
import "./App.css";

export default function App() {
  const [todos, setTodos] = useState([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  // Wrap every API call so failures show a message instead of failing silently.
  async function run(action) {
    try {
      setError("");
      await action();
    } catch (err) {
      setError(err.message);
    }
  }

  const refresh = async () => setTodos(await listTodos());

  useEffect(() => {
    run(refresh);
  }, []);

  function handleAdd(e) {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    run(async () => {
      await createTodo(trimmed);
      setTitle("");
      await refresh();
    });
  }

  const handleToggle = (todo) =>
    run(async () => {
      await updateTodo({ ...todo, done: !todo.done });
      await refresh();
    });

  const handleDelete = (id) =>
    run(async () => {
      await deleteTodo(id);
      await refresh();
    });

  return (
    <main>
      <h1>Todos</h1>
      <form onSubmit={handleAdd}>
        <input
          aria-label="New todo"
          placeholder="What needs doing?"
          value={title}
          maxLength={200}
          onChange={(e) => setTitle(e.target.value)}
        />
        <button type="submit">Add</button>
      </form>
      {error && <p role="alert">{error}</p>}
      <ul>
        {todos.map((todo) => (
          <li key={todo.id} className={todo.done ? "done" : ""}>
            <label>
              <input type="checkbox" checked={todo.done} onChange={() => handleToggle(todo)} />
              {todo.title}
            </label>
            <button aria-label={`Delete ${todo.title}`} onClick={() => handleDelete(todo.id)}>
              ✕
            </button>
          </li>
        ))}
      </ul>
      {todos.length === 0 && !error && <p>Nothing yet. Add your first todo.</p>}
    </main>
  );
}
