"""Import-walking: recursion, circular imports, broken modules."""

import sys

import pytest

from sqlalchemy_annotate.discovery import discover_models
from sqlalchemy_annotate.errors import DiscoveryError
from tests.conftest import write_package

BASE = """
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass
"""


@pytest.fixture
def add_to_path(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]


def test_recursive_discovery(add_to_path):
    write_package(add_to_path, {
        "app/__init__.py": "",
        "app/models/__init__.py": "",
        "app/models/base.py": BASE,
        "app/models/user.py": """
            from app.models.base import Base
            from sqlalchemy.orm import Mapped, mapped_column
            class User(Base):
                __tablename__ = "users"
                id: Mapped[int] = mapped_column(primary_key=True)
        """,
        "app/models/post.py": """
            from app.models.base import Base
            from sqlalchemy.orm import Mapped, mapped_column
            class Post(Base):
                __tablename__ = "posts"
                id: Mapped[int] = mapped_column(primary_key=True)
        """,
    })
    result = discover_models("app.models")
    names = {m.qualname for m in result.models}
    assert {"User", "Post"} <= names
    assert result.import_errors == {}


def test_broken_module_is_reported_not_fatal(add_to_path):
    write_package(add_to_path, {
        "app/__init__.py": "",
        "app/models/__init__.py": "",
        "app/models/base.py": BASE,
        "app/models/good.py": """
            from app.models.base import Base
            from sqlalchemy.orm import Mapped, mapped_column
            class Good(Base):
                __tablename__ = "good"
                id: Mapped[int] = mapped_column(primary_key=True)
        """,
        "app/models/broken.py": "import a_module_that_does_not_exist\n",
    })
    result = discover_models("app.models")
    assert any(m.qualname == "Good" for m in result.models)
    assert any("broken" in mod for mod in result.import_errors)


def test_circular_imports_still_discover(add_to_path):
    write_package(add_to_path, {
        "app/__init__.py": "",
        "app/models/__init__.py": "",
        "app/models/base.py": BASE,
        "app/models/a.py": """
            from app.models.base import Base
            from sqlalchemy.orm import Mapped, mapped_column, relationship
            class A(Base):
                __tablename__ = "a"
                id: Mapped[int] = mapped_column(primary_key=True)
                bs: Mapped[list["B"]] = relationship()
            from app.models import b  # noqa: E402  (circular on purpose)
        """,
        "app/models/b.py": """
            from app.models.base import Base
            from app.models.a import A
            from sqlalchemy import ForeignKey
            from sqlalchemy.orm import Mapped, mapped_column
            class B(Base):
                __tablename__ = "b"
                id: Mapped[int] = mapped_column(primary_key=True)
                a_id: Mapped[int] = mapped_column(ForeignKey("a.id"))
        """,
    })
    result = discover_models("app.models")
    names = {m.qualname for m in result.models}
    assert {"A", "B"} <= names


def test_unknown_package_raises():
    with pytest.raises(DiscoveryError):
        discover_models("definitely.not.a.package.anywhere")
