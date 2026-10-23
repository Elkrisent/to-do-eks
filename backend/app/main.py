from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import Base, engine, get_session
from app.models import Todo, TodoCreate, TodoOut, TodoUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Demo-grade: create the table on startup instead of using migrations.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Todo API", lifespan=lifespan)

SessionDep = Annotated[Session, Depends(get_session)]


@app.get("/api/healthz")
def healthz(session: SessionDep):
    # Touches the DB so Kubernetes readiness fails if Postgres is unreachable.
    try:
        session.execute(text("SELECT 1"))
    except Exception as err:
        raise HTTPException(status_code=503, detail="database unavailable") from err
    return {"status": "ok"}


@app.get("/api/todos", response_model=list[TodoOut])
def list_todos(session: SessionDep):
    return session.scalars(select(Todo).order_by(Todo.id)).all()


@app.post("/api/todos", response_model=TodoOut, status_code=201)
def create_todo(body: TodoCreate, session: SessionDep):
    todo = Todo(title=body.title, done=body.done)
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo


def _get_or_404(session: Session, todo_id: int) -> Todo:
    todo = session.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="todo not found")
    return todo


@app.get("/api/todos/{todo_id}", response_model=TodoOut)
def get_todo(todo_id: int, session: SessionDep):
    return _get_or_404(session, todo_id)


@app.put("/api/todos/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: int, body: TodoUpdate, session: SessionDep):
    todo = _get_or_404(session, todo_id)
    todo.title = body.title
    todo.done = body.done
    session.commit()
    session.refresh(todo)
    return todo


@app.delete("/api/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int, session: SessionDep):
    todo = _get_or_404(session, todo_id)
    session.delete(todo)
    session.commit()
    return Response(status_code=204)
