"""Metadata extraction across SQLAlchemy 2.x features (no DB connection)."""

import enum

import pytest
from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sqlalchemy_annotate.config import Config
from sqlalchemy_annotate.schema import resolve_dialect
from tests.conftest import schema_for


@pytest.fixture
def Base():
    class _Base(DeclarativeBase):
        pass

    return _Base


def test_v2_mapped_column(Base, config, pg_dialect):
    class User(Base):
        __tablename__ = "users"
        id: Mapped[int] = mapped_column(primary_key=True)
        email: Mapped[str] = mapped_column(String(255))
        nick: Mapped[str | None]

    s = schema_for(User, config, pg_dialect)
    cols = {c.name: c for c in s.columns}
    assert cols["id"].primary_key and not cols["id"].nullable
    assert cols["email"].type_ == "varchar(255)" and not cols["email"].nullable
    assert cols["nick"].nullable


def test_legacy_column_syntax(Base, config, pg_dialect):
    class Legacy(Base):
        __tablename__ = "legacy"
        id = Column(Integer, primary_key=True)
        name = Column(String(50), nullable=False)

    s = schema_for(Legacy, config, pg_dialect)
    cols = {c.name: c for c in s.columns}
    assert cols["id"].primary_key
    assert cols["name"].type_ == "varchar(50)"


def test_composite_primary_key(Base, config, pg_dialect):
    class Membership(Base):
        __tablename__ = "memberships"
        user_id: Mapped[int] = mapped_column(primary_key=True)
        group_id: Mapped[int] = mapped_column(primary_key=True)

    s = schema_for(Membership, config, pg_dialect)
    assert s.composite_pk
    assert set(s.primary_key) == {"user_id", "group_id"}


def test_enum_values(Base, config, pg_dialect):
    class Color(enum.Enum):
        red = "red"
        green = "green"

    class Paint(Base):
        __tablename__ = "paints"
        id: Mapped[int] = mapped_column(primary_key=True)
        color: Mapped[Color] = mapped_column(Enum(Color))

    s = schema_for(Paint, config, pg_dialect)
    color = next(c for c in s.columns if c.name == "color")
    assert color.enum_values == ("red", "green")


def test_indexes_and_foreign_keys(Base, config, pg_dialect):
    class Account(Base):
        __tablename__ = "accounts"
        id: Mapped[int] = mapped_column(primary_key=True)
        owner_id: Mapped[int] = mapped_column(
            ForeignKey("users.id", ondelete="CASCADE"), index=True
        )

    s = schema_for(Account, config, pg_dialect)
    assert any(fk.referred_table == "users" for fk in s.foreign_keys)
    assert s.foreign_keys[0].ondelete == "CASCADE"
    assert any(ix.columns == ("owner_id",) for ix in s.indexes)


def test_relationship_direction(Base, config, pg_dialect):
    class Author(Base):
        __tablename__ = "authors"
        id: Mapped[int] = mapped_column(primary_key=True)
        books: Mapped[list["Book"]] = relationship(back_populates="author")

    class Book(Base):
        __tablename__ = "books"
        id: Mapped[int] = mapped_column(primary_key=True)
        author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
        author: Mapped[Author] = relationship(back_populates="books")

    cfg = Config(include_relationships=True)
    s = schema_for(Author, cfg, pg_dialect)
    rel = next(r for r in s.relationships if r.name == "books")
    assert rel.direction == "one-to-many" and rel.target == "Book"


def test_joined_table_inheritance(Base, config, pg_dialect):
    class Employee(Base):
        __tablename__ = "employees"
        id: Mapped[int] = mapped_column(primary_key=True)
        type: Mapped[str] = mapped_column(String(50))
        __mapper_args__ = {"polymorphic_on": "type", "polymorphic_identity": "e"}

    class Manager(Employee):
        __tablename__ = "managers"
        id: Mapped[int] = mapped_column(ForeignKey("employees.id"), primary_key=True)
        __mapper_args__ = {"polymorphic_identity": "m"}

    s = schema_for(Manager, config, pg_dialect)
    # local_table is the child's own table, not the parent's.
    assert s.table_name == "managers"


def test_async_engine_resolves_sync_dialect():
    d = resolve_dialect(Config(engine="postgresql+asyncpg://u:p@h/db"))
    assert d.name == "postgresql"


def test_excluded_tables_return_none(Base, pg_dialect):
    class AuditLog(Base):
        __tablename__ = "audit_log"
        id: Mapped[int] = mapped_column(primary_key=True)

    cfg = Config(exclude=("audit_*",))
    assert schema_for(AuditLog, cfg, pg_dialect) is None
