"""End-to-end CLI: generate / check / remove exit codes and behaviour."""

import sys

import pytest
from typer.testing import CliRunner

from sqlalchemy_annotate.cli import app
from tests.conftest import write_package

runner = CliRunner()

PROJECT = {
    "myapp/__init__.py": "",
    "myapp/models/__init__.py": "from myapp.models.user import User\n",
    "myapp/models/base.py": (
        "from sqlalchemy.orm import DeclarativeBase\n"
        "class Base(DeclarativeBase):\n    pass\n"
    ),
    "myapp/models/user.py": (
        "from myapp.models.base import Base\n"
        "from sqlalchemy.orm import Mapped, mapped_column\n\n\n"
        "class User(Base):\n"
        '    __tablename__ = "users"\n'
        "    id: Mapped[int] = mapped_column(primary_key=True)\n"
    ),
}


@pytest.fixture
def project(tmp_path, monkeypatch):
    write_package(tmp_path, PROJECT)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.sqlalchemy-annotate]\nmodels = "myapp.models"\n'
    )
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    for name in list(sys.modules):
        if name == "myapp" or name.startswith("myapp."):
            del sys.modules[name]


def _user_src(project):
    return (project / "myapp/models/user.py").read_text()


def test_generate_then_check_then_remove(project):
    r = runner.invoke(app, ["generate"])
    assert r.exit_code == 0, r.output
    assert "# == Schema Information" in _user_src(project)
    assert "# Table name: users" in _user_src(project)

    # check is clean right after generate
    assert runner.invoke(app, ["check"]).exit_code == 0

    # remove strips it, check now fails (stale)
    assert runner.invoke(app, ["remove"]).exit_code == 0
    assert "# == Schema Information" not in _user_src(project)
    assert runner.invoke(app, ["check"]).exit_code == 1


def test_check_detects_stale(project):
    runner.invoke(app, ["generate"])
    # Mutate the model so the annotation goes stale.
    p = project / "myapp/models/user.py"
    p.write_text(p.read_text().replace(
        "id: Mapped[int] = mapped_column(primary_key=True)",
        "id: Mapped[int] = mapped_column(primary_key=True)\n"
        "    name: Mapped[str] = mapped_column()",
    ))
    # Each real CLI run is a fresh process; CliRunner is in-process, so drop
    # the cached modules to simulate that and pick up the edited file.
    for name in list(sys.modules):
        if name == "myapp" or name.startswith("myapp."):
            del sys.modules[name]
    r = runner.invoke(app, ["check"])
    assert r.exit_code == 1


def test_dry_run_writes_nothing(project):
    before = _user_src(project)
    r = runner.invoke(app, ["generate", "--dry-run"])
    assert r.exit_code == 0
    assert _user_src(project) == before
    assert "would change" in r.output


def test_missing_models_config_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["generate", "--config", "/dev/null"])
    assert r.exit_code != 0


def test_version_flag():
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0
    assert "sqlalchemy-annotate" in r.output
