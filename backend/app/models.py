from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    done: Mapped[bool] = mapped_column(Boolean, default=False)


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    done: bool = False


class TodoUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    done: bool


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    done: bool
