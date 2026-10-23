// Relative URLs: in dev Vite proxies /api, in compose/EKS the same origin serves both.
async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.status === 204 ? null : res.json();
}

export const listTodos = () => request("/todos");

export const createTodo = (title) =>
  request("/todos", { method: "POST", body: JSON.stringify({ title }) });

export const updateTodo = (todo) =>
  request(`/todos/${todo.id}`, {
    method: "PUT",
    body: JSON.stringify({ title: todo.title, done: todo.done }),
  });

export const deleteTodo = (id) => request(`/todos/${id}`, { method: "DELETE" });
