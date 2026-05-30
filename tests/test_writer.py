"""CST rewriting: idempotency, preservation, multi-class, malformed input."""

import pytest

from sqlalchemy_annotate.config import Config
from sqlalchemy_annotate.errors import ParseError
from sqlalchemy_annotate.models import ColumnInfo, ModelSchema
from sqlalchemy_annotate.writer import annotate_source, remove_source

CFG = Config()
TOP = Config(position="top")


def _schema(qualname: str, table: str) -> ModelSchema:
    return ModelSchema(
        class_qualname=qualname,
        table_name=table,
        source_file="m.py",
        columns=(ColumnInfo("id", "integer", nullable=False, primary_key=True),),
    )


def test_inserts_block_below_class_by_default():
    src = "class User:\n    pass\n"
    out = annotate_source(src, "m.py", {"User": _schema("User", "users")}, CFG)
    assert out.changed
    assert out.new_source.startswith("class User:")
    assert "# Table name: users" in out.new_source
    body_end = out.new_source.index("pass")
    block_start = out.new_source.index("# == Schema Information")
    assert body_end < block_start
    assert "# == End Schema Information" in out.new_source


def test_inserts_block_above_class_in_top_mode():
    src = "class User:\n    pass\n"
    out = annotate_source(src, "m.py", {"User": _schema("User", "users")}, TOP)
    assert out.changed
    assert out.new_source.startswith("# == Schema Information")
    assert "# Table name: users" in out.new_source
    assert out.new_source.rstrip().endswith("pass")


def test_idempotent_bottom():
    src = "import os\n\n\nclass User:\n    pass\n"
    schemas = {"User": _schema("User", "users")}
    once = annotate_source(src, "m.py", schemas, CFG).new_source
    twice = annotate_source(once, "m.py", schemas, CFG)
    assert not twice.changed
    assert twice.new_source == once


def test_idempotent_top():
    src = "import os\n\n\nclass User:\n    pass\n"
    schemas = {"User": _schema("User", "users")}
    once = annotate_source(src, "m.py", schemas, TOP).new_source
    twice = annotate_source(once, "m.py", schemas, TOP)
    assert not twice.changed
    assert twice.new_source == once


def test_replaces_stale_block_only():
    src = "import os\n\n\nclass User:\n    pass\n"
    first = annotate_source(src, "m.py", {"User": _schema("User", "OLD")}, CFG).new_source
    second = annotate_source(first, "m.py", {"User": _schema("User", "users")}, CFG)
    assert second.changed
    assert "# Table name: users" in second.new_source
    assert "OLD" not in second.new_source
    assert second.new_source.count("# == Schema Information") == 1


def test_preserves_imports_comments_and_formatting():
    src = (
        "import os  # keep me\n"
        "from x import y\n\n\n"
        "# a standalone comment\n"
        "class User:\n"
        '    """doc."""\n'
        "    x = 1\n"
    )
    out = annotate_source(src, "m.py", {"User": _schema("User", "users")}, CFG).new_source
    assert "import os  # keep me" in out
    assert "from x import y" in out
    assert "# a standalone comment" in out
    assert '"""doc."""' in out


def test_multiple_models_one_file_bottom():
    src = "class A:\n    pass\n\n\nclass B:\n    pass\n"
    schemas = {"A": _schema("A", "a_tbl"), "B": _schema("B", "b_tbl")}
    out = annotate_source(src, "m.py", schemas, CFG).new_source
    assert "# Table name: a_tbl" in out and "# Table name: b_tbl" in out
    assert out.count("# == Schema Information") == 2
    # Block for A appears between the two classes; block for B appears at EOF.
    assert out.index("a_tbl") < out.index("class B")
    assert out.index("class B") < out.index("b_tbl")
    # Unrelated class is left alone.
    out2 = annotate_source(
        src + "\n\nclass C:\n    pass\n", "m.py", schemas, CFG
    ).new_source
    assert out2.count("# == Schema Information") == 2


def test_unmapped_class_untouched():
    src = "class Helper:\n    pass\n"
    out = annotate_source(src, "m.py", {"User": _schema("User", "users")}, CFG)
    assert not out.changed


def test_remove_round_trips_bottom():
    src = "import os\n\n\nclass User:\n    pass\n"
    annotated = annotate_source(src, "m.py", {"User": _schema("User", "users")}, CFG).new_source
    removed = remove_source(annotated, "m.py", CFG)
    assert removed.changed
    assert removed.new_source == src


def test_remove_round_trips_top():
    src = "import os\n\n\nclass User:\n    pass\n"
    annotated = annotate_source(src, "m.py", {"User": _schema("User", "users")}, TOP).new_source
    removed = remove_source(annotated, "m.py", TOP)
    assert removed.changed
    assert removed.new_source == src


def test_remove_strips_block_regardless_of_current_position():
    """remove should clear blocks whether they were originally placed top or bottom."""
    src = "class User:\n    pass\n"
    schemas = {"User": _schema("User", "users")}
    annotated_top = annotate_source(src, "m.py", schemas, TOP).new_source
    # Removing while configured for bottom still cleans up top-placed blocks.
    assert remove_source(annotated_top, "m.py", CFG).new_source == src
    annotated_bot = annotate_source(src, "m.py", schemas, CFG).new_source
    assert remove_source(annotated_bot, "m.py", TOP).new_source == src


def test_decorated_class_top_mode_above_decorator():
    src = "import dataclasses\n\n\n@dataclasses.dataclass\nclass User:\n    pass\n"
    out = annotate_source(src, "m.py", {"User": _schema("User", "users")}, TOP).new_source
    assert out.index("# == Schema Information") < out.index("@dataclasses.dataclass")


def test_decorated_class_bottom_mode_after_class():
    src = "import dataclasses\n\n\n@dataclasses.dataclass\nclass User:\n    pass\n"
    out = annotate_source(src, "m.py", {"User": _schema("User", "users")}, CFG).new_source
    assert out.index("@dataclasses.dataclass") < out.index("# == Schema Information")
    assert out.index("pass") < out.index("# == Schema Information")


def test_switching_position_replaces_block():
    src = "class User:\n    pass\n"
    schemas = {"User": _schema("User", "users")}
    bottom_first = annotate_source(src, "m.py", schemas, CFG).new_source
    flipped = annotate_source(bottom_first, "m.py", schemas, TOP).new_source
    assert flipped.startswith("# == Schema Information")
    assert flipped.count("# == Schema Information") == 1
    # And back again.
    flipped_back = annotate_source(flipped, "m.py", schemas, CFG).new_source
    assert flipped_back.count("# == Schema Information") == 1
    assert flipped_back.startswith("class User:")


def test_malformed_file_raises_parse_error():
    with pytest.raises(ParseError):
        annotate_source("class User(:\n", "bad.py", {"User": _schema("User", "u")}, CFG)
