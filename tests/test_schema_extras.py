"""Defaults, server defaults, normalization, dialect fallback, M2M."""

import pytest
from sqlalchemy import Column, ForeignKey, String, Table, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sqlalchemy_annotate.config import Config
from sqlalchemy_annotate.schema import resolve_dialect
from tests.conftest import schema_for


@pytest.fixture
def Base():
    class _Base(DeclarativeBase):
        pass

    return _Base


def test_normalize_types_rails_style(Base, pg_dialect):
    class Thing(Base):
        __tablename__ = "things"
        id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
        name: Mapped[str] = mapped_column(String)  # no length

    cfg = Config(normalize_types=True)
    cols = {c.name: c for c in schema_for(Thing, cfg, pg_dialect).columns}
    assert cols["id"].type_ == "bigint"
    assert cols["name"].type_ == "varchar(255)"

    # Truthful by default: no fabrication.
    truthful = {c.name: c for c in schema_for(Thing, Config(), pg_dialect).columns}
    assert truthful["id"].type_ == "integer"
    assert truthful["name"].type_ == "varchar"


def test_scalar_and_callable_defaults(Base, pg_dialect):
    def make_token() -> str:
        return "x"

    class Defaulted(Base):
        __tablename__ = "defaulted"
        id: Mapped[int] = mapped_column(primary_key=True)
        active: Mapped[bool] = mapped_column(default=True)
        token: Mapped[str] = mapped_column(default=make_token)

    cols = {c.name: c for c in schema_for(Defaulted, Config(), pg_dialect).columns}
    assert cols["active"].default == "True"
    assert cols["token"].default == "make_token()"


def test_server_default_text(Base, pg_dialect):
    class Stamped(Base):
        __tablename__ = "stamped"
        id: Mapped[int] = mapped_column(primary_key=True)
        created_at: Mapped[str] = mapped_column(server_default=func.now())
        flag: Mapped[bool] = mapped_column(server_default=text("false"))

    cols = {c.name: c for c in schema_for(Stamped, Config(), pg_dialect).columns}
    assert "now()" in cols["created_at"].server_default
    assert cols["flag"].server_default == "false"


def test_unparseable_engine_falls_back_to_postgres():
    assert resolve_dialect(Config(engine="::::nonsense")).name == "postgresql"


def test_explicit_dialect_override():
    assert resolve_dialect(Config(dialect="sqlite")).name == "sqlite"
    assert resolve_dialect(Config(dialect="mysql")).name == "mysql"


def test_many_to_many_relationship(Base, pg_dialect):
    assoc = Table(
        "user_groups",
        Base.metadata,
        Column("user_id", ForeignKey("m2m_users.id"), primary_key=True),
        Column("group_id", ForeignKey("m2m_groups.id"), primary_key=True),
    )

    class Group(Base):
        __tablename__ = "m2m_groups"
        id: Mapped[int] = mapped_column(primary_key=True)

    class MUser(Base):
        __tablename__ = "m2m_users"
        id: Mapped[int] = mapped_column(primary_key=True)
        groups: Mapped[list[Group]] = relationship(secondary=assoc)

    cfg = Config(include_relationships=True)
    s = schema_for(MUser, cfg, pg_dialect)
    rel = next(r for r in s.relationships if r.name == "groups")
    assert rel.direction == "many-to-many" and rel.target == "Group"


def test_legacy_column_composite_fk(Base, pg_dialect):
    from sqlalchemy import ForeignKeyConstraint

    class Parent(Base):
        __tablename__ = "parent"
        a = Column(String(5), primary_key=True)
        b = Column(String(5), primary_key=True)

    class Child(Base):
        __tablename__ = "child"
        id = Column(String(5), primary_key=True)
        pa = Column(String(5))
        pb = Column(String(5))
        __table_args__ = (
            ForeignKeyConstraint(["pa", "pb"], ["parent.a", "parent.b"]),
        )

    s = schema_for(Child, Config(), pg_dialect)
    fk = s.foreign_keys[0]
    assert fk.columns == ("pa", "pb")
    assert fk.referred_table == "parent"
    assert fk.referred_columns == ("a", "b")
