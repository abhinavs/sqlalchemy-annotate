# Contributing

Thanks for considering a contribution.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # or: uv pip install -e ".[dev]"
pre-commit install             # optional but recommended
```

## Before opening a PR

```bash
ruff check src tests
pytest -q --cov=sqlalchemy_annotate --cov-report=term-missing
```

- New behaviour needs a test. The `schema`, `formatter`, `parser` and `writer`
  modules are pure or near-pure by design; keep them that way and test them in
  isolation.
- The single most important invariant is **idempotency**: running `generate`
  twice must produce no diff. `tests/test_writer.py::test_idempotent` guards
  this; add cases there when touching `parser.py` / `writer.py`.
- Never reach for regex to edit source files. All rewriting goes through the
  libcst transformer in `writer.py`.
- Keep heavy imports (`sqlalchemy`, `libcst`) inside command bodies so the CLI
  stays fast to start.
- Update `CHANGELOG.md` under `## [Unreleased]`.

## Releasing

1. Move the `Unreleased` notes into a new version section in `CHANGELOG.md`.
2. Bump `__version__` in `src/sqlalchemy_annotate/__init__.py` (the build and
   the runtime version are single-sourced from there).
3. Tag `vX.Y.Z`; CI builds and the tag drives the changelog links.
