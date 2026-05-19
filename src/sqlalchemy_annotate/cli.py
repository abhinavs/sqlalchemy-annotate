"""Typer CLI.

Only ``typer``/``rich`` import at module load; SQLAlchemy, libcst and the user's
model code are imported inside command bodies so ``--help`` / ``--version``
stay fast even in projects with hundreds of models.
"""

from __future__ import annotations

import difflib
from collections import defaultdict
from pathlib import Path

import typer
from rich.console import Console

from sqlalchemy_annotate import __version__

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Maintain Rails-style schema annotations in SQLAlchemy model files.",
)
console = Console()
err_console = Console(stderr=True)

# Shared options (typer has no global option groups, so we repeat the few we need).
_Models = typer.Option(None, "--models", help="Dotted path to the models package.")
_Engine = typer.Option(None, "--engine", help="DB URL; only its dialect is used (no connect).")
_Dialect = typer.Option(None, "--dialect", help="Force a dialect (postgresql, mysql, ...).")
_ConfigPath = typer.Option(None, "--config", help="Path to a pyproject.toml.")
_Exclude = typer.Option(None, "--exclude", help="Glob of table names to skip (repeatable).")
_Sort = typer.Option(None, "--sort", help="definition | alphabetical")
_DryRun = typer.Option(False, "--dry-run", help="Show what would change; write nothing.")


def _build(models, engine, dialect, config_path, exclude, sort, **flags):
    """Discover models and build {file: {qualname: ModelSchema}}."""
    from sqlalchemy_annotate.config import load_config
    from sqlalchemy_annotate.discovery import discover_models
    from sqlalchemy_annotate.schema import build_schema, resolve_dialect

    overrides = {
        "models": models, "engine": engine, "dialect": dialect,
        "exclude": list(exclude) if exclude else None, "sort": sort, **flags,
    }
    cfg = load_config(
        config_path=Path(config_path) if config_path else None,
        cli_overrides=overrides,
    )
    if not cfg.models:
        raise typer.BadParameter(
            "no models package configured; pass --models or set "
            "[tool.sqlalchemy-annotate].models in pyproject.toml"
        )

    result = discover_models(cfg.models)
    for mod, msg in result.import_errors.items():
        err_console.print(f"[yellow]warning[/]: skipped {mod}: {msg}")

    sa_dialect = resolve_dialect(cfg)
    by_file: dict[str, dict] = defaultdict(dict)
    for model in result.models:
        schema = build_schema(model, cfg, sa_dialect)
        if schema is not None:
            by_file[schema.source_file][schema.class_qualname] = schema
    return cfg, by_file


def _diff(path: str, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
        )
    )


@app.command()
def generate(
    models: str | None = _Models,
    engine: str | None = _Engine,
    dialect: str | None = _Dialect,
    config: str | None = _ConfigPath,
    exclude: list[str] | None = _Exclude,
    sort: str | None = _Sort,
    include_indexes: bool | None = typer.Option(None, "--include-indexes/--no-indexes"),
    include_foreign_keys: bool | None = typer.Option(
        None, "--include-foreign-keys/--no-foreign-keys"
    ),
    include_relationships: bool | None = typer.Option(
        None, "--include-relationships/--no-relationships"
    ),
    normalize_types: bool | None = typer.Option(None, "--normalize-types/--no-normalize-types"),
    dry_run: bool = _DryRun,
) -> None:
    """Add or refresh the schema annotation block in each model file."""
    from sqlalchemy_annotate.errors import AnnotateError
    from sqlalchemy_annotate.writer import annotate_source

    try:
        cfg, by_file = _build(
            models, engine, dialect, config, exclude, sort,
            include_indexes=include_indexes,
            include_foreign_keys=include_foreign_keys,
            include_relationships=include_relationships,
            normalize_types=normalize_types,
        )
    except AnnotateError as exc:
        err_console.print(f"[red]error[/]: {exc}")
        raise typer.Exit(2) from exc

    changed = 0
    for path, schemas in sorted(by_file.items()):
        src = Path(path).read_text(encoding="utf-8")
        try:
            res = annotate_source(src, path, schemas, cfg)
        except AnnotateError as exc:
            err_console.print(f"[yellow]warning[/]: {exc}")
            continue
        if res.changed:
            changed += 1
            if dry_run:
                console.print(_diff(path, src, res.new_source))
            else:
                Path(path).write_text(res.new_source, encoding="utf-8")
            console.print(f"[green]annotated[/] {path}")
        else:
            console.print(f"[dim]unchanged[/] {path}")
    verb = "would change" if dry_run else "changed"
    console.print(f"\n{changed} file(s) {verb}, {len(by_file)} scanned.")


@app.command()
def check(
    models: str | None = _Models,
    engine: str | None = _Engine,
    dialect: str | None = _Dialect,
    config: str | None = _ConfigPath,
    exclude: list[str] | None = _Exclude,
    sort: str | None = _Sort,
) -> None:
    """Exit 0 if every annotation is current, 1 if any is stale (CI-friendly)."""
    from sqlalchemy_annotate.errors import AnnotateError
    from sqlalchemy_annotate.writer import annotate_source

    try:
        cfg, by_file = _build(models, engine, dialect, config, exclude, sort)
    except AnnotateError as exc:
        err_console.print(f"[red]error[/]: {exc}")
        raise typer.Exit(2) from exc

    stale = []
    for path, schemas in sorted(by_file.items()):
        src = Path(path).read_text(encoding="utf-8")
        try:
            res = annotate_source(src, path, schemas, cfg)
        except AnnotateError as exc:
            err_console.print(f"[yellow]warning[/]: {exc}")
            continue
        if res.changed:
            stale.append(path)
            console.print(_diff(path, src, res.new_source))

    if stale:
        err_console.print(f"[red]{len(stale)} file(s) have stale annotations.[/]")
        raise typer.Exit(1)
    console.print("[green]All annotations are up to date.[/]")


@app.command()
def remove(
    models: str | None = _Models,
    engine: str | None = _Engine,
    dialect: str | None = _Dialect,
    config: str | None = _ConfigPath,
    exclude: list[str] | None = _Exclude,
    dry_run: bool = _DryRun,
) -> None:
    """Strip every annotation block, leaving the rest of each file intact."""
    from sqlalchemy_annotate.errors import AnnotateError
    from sqlalchemy_annotate.writer import remove_source

    try:
        cfg, by_file = _build(models, engine, dialect, config, exclude, None)
    except AnnotateError as exc:
        err_console.print(f"[red]error[/]: {exc}")
        raise typer.Exit(2) from exc

    changed = 0
    for path in sorted(by_file):
        src = Path(path).read_text(encoding="utf-8")
        try:
            res = remove_source(src, path, cfg)
        except AnnotateError as exc:
            err_console.print(f"[yellow]warning[/]: {exc}")
            continue
        if res.changed:
            changed += 1
            if dry_run:
                console.print(_diff(path, src, res.new_source))
            else:
                Path(path).write_text(res.new_source, encoding="utf-8")
            console.print(f"[green]cleaned[/] {path}")
    verb = "would change" if dry_run else "changed"
    console.print(f"\n{changed} file(s) {verb}.")


def _version(value: bool) -> None:
    if value:
        console.print(f"sqlalchemy-annotate {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version, is_eager=True, help="Show version."
    ),
) -> None:
    """Maintain Rails-style schema annotations in SQLAlchemy model files."""
