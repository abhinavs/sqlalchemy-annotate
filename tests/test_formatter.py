"""Pure rendering tests: ModelSchema in, comment lines out."""

from sqlalchemy_annotate.config import Config
from sqlalchemy_annotate.formatter import END_MARKER, START_MARKER, render_block
from sqlalchemy_annotate.models import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    ModelSchema,
    RelationshipInfo,
)


def _schema(**kw) -> ModelSchema:
    base = dict(class_qualname="User", table_name="users", source_file="u.py")
    base.update(kw)
    return ModelSchema(**base)


def test_markers_and_table_name():
    out = render_block(_schema(columns=(
        ColumnInfo("id", "integer", nullable=False, primary_key=True),
    )), Config())
    assert out[0] == START_MARKER
    assert out[-1] == END_MARKER
    assert "# Table name: users" in out


def test_column_flags_alignment_and_text():
    out = render_block(_schema(columns=(
        ColumnInfo("id", "integer", nullable=False, primary_key=True),
        ColumnInfo("email", "varchar", nullable=False, primary_key=False),
        ColumnInfo("bio", "text", nullable=True, primary_key=False),
    )), Config())
    assert "# id    : integer, primary key" in out
    assert "# email : varchar, not null" in out
    assert "# bio   : text" in out  # nullable -> no extra flag


def test_composite_pk_line():
    out = render_block(_schema(primary_key=("a", "b"), columns=(
        ColumnInfo("a", "integer", nullable=False, primary_key=True),
        ColumnInfo("b", "integer", nullable=False, primary_key=True),
    )), Config())
    assert "# Composite primary key: a, b" in out


def test_indexes_and_fk_sections_toggle():
    schema = _schema(
        columns=(ColumnInfo("id", "integer", nullable=False, primary_key=True),),
        indexes=(IndexInfo("ix_users_email", ("email",), unique=True),),
        foreign_keys=(ForeignKeyInfo(("profile_id",), "profiles", ("id",), "CASCADE"),),
    )
    on = render_block(schema, Config(include_indexes=True, include_foreign_keys=True))
    assert "#   ix_users_email (email) UNIQUE" in on
    assert "#   profile_id -> profiles.id (ON DELETE CASCADE)" in on

    off = render_block(schema, Config(include_indexes=False, include_foreign_keys=False))
    assert not any("Indexes" in line for line in off)
    assert not any("Foreign Keys" in line for line in off)


def test_relationships_only_when_enabled():
    schema = _schema(
        columns=(ColumnInfo("id", "integer", nullable=False, primary_key=True),),
        relationships=(RelationshipInfo("posts", "Post", "one-to-many"),),
    )
    assert not any("Relationships" in line for line in render_block(schema, Config()))
    on = render_block(schema, Config(include_relationships=True))
    assert "#   posts (one-to-many Post)" in on


def test_alphabetical_sort():
    schema = _schema(columns=(
        ColumnInfo("zeta", "integer", nullable=True, primary_key=False),
        ColumnInfo("alpha", "integer", nullable=True, primary_key=False),
    ))
    out = render_block(schema, Config(sort="alphabetical"))
    cols = [line for line in out if line.startswith("# alpha") or line.startswith("# zeta")]
    assert cols[0].startswith("# alpha")
