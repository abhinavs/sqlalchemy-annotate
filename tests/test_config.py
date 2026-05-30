"""Config precedence and validation."""

import pytest

from sqlalchemy_annotate.config import load_config
from sqlalchemy_annotate.errors import ConfigError

PYPROJECT = """
[tool.sqlalchemy-annotate]
models = "app.models"
include_indexes = false
sort = "alphabetical"
exclude = ["audit_*", "tmp_*"]
"""


def test_reads_pyproject_section(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    cfg = load_config(config_path=tmp_path / "pyproject.toml")
    assert cfg.models == "app.models"
    assert cfg.include_indexes is False
    assert cfg.sort == "alphabetical"
    assert cfg.exclude == ("audit_*", "tmp_*")


def test_cli_overrides_win(tmp_path):
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    cfg = load_config(
        config_path=tmp_path / "pyproject.toml",
        cli_overrides={"models": "other.models", "sort": None},
    )
    assert cfg.models == "other.models"  # override applied
    assert cfg.sort == "alphabetical"    # None override ignored


def test_defaults_when_no_file(tmp_path):
    cfg = load_config(config_path=tmp_path / "missing.toml")
    assert cfg.include_foreign_keys is True
    assert cfg.normalize_types is False


def test_position_default_is_bottom(tmp_path):
    cfg = load_config(config_path=tmp_path / "missing.toml")
    assert cfg.position == "bottom"


def test_position_read_from_pyproject(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text('[tool.sqlalchemy-annotate]\nposition = "top"\n')
    cfg = load_config(config_path=p)
    assert cfg.position == "top"


def test_invalid_position_rejected(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text('[tool.sqlalchemy-annotate]\nposition = "sideways"\n')
    with pytest.raises(ConfigError):
        load_config(config_path=p)


def test_invalid_sort_rejected(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text("[tool.sqlalchemy-annotate]\nsort = \"sideways\"\n")
    with pytest.raises(ConfigError):
        load_config(config_path=p)


def test_unknown_key_rejected(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text("[tool.sqlalchemy-annotate]\nnope = true\n")
    with pytest.raises(ConfigError):
        load_config(config_path=p)
