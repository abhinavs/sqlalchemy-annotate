# sqlalchemy-annotate

Rails `annotate_models` for modern SQLAlchemy 2.x + Alembic projects.

It keeps a Schema Information comment block alongside every model class, in
sync with your actual SQLAlchemy metadata, so reviewers and editors see the
table shape without opening a database or a migration. The block sits below
the class by default; flip `position = "top"` to put it above instead.

```python
class User(Base):
    __tablename__ = "users"
    ...

# == Schema Information
#
# Table name: users
#
# id         : integer, primary key
# email      : varchar, not null
# created_at : timestamp
#
# Indexes
#   ix_users_email (email) UNIQUE
#
# Foreign Keys
#   profile_id -> profiles.id (ON DELETE CASCADE)
#
# == End Schema Information
```

## Why it is safe

- **No database required.** Everything is read from `Base.metadata` /
  `__table__`. A connection URL, if you pass one, is parsed only for its
  dialect so types compile correctly offline. No engine is ever connected.
- **No regex rewriting.** Files are edited through a single
  [libcst](https://github.com/Instagram/LibCST) transformer. Imports,
  comments, blank lines and Black formatting are preserved byte-for-byte;
  only the region between the markers is touched.
- **Idempotent.** Running `generate` twice produces no diff, which is what
  makes `check` reliable in CI and pre-commit.

## Install

```bash
pip install sqlalchemy-annotate      # or: uv pip install sqlalchemy-annotate
```

## Usage

```bash
sqlalchemy-annotate generate
sqlalchemy-annotate generate --models app.models --engine postgresql://localhost/db
sqlalchemy-annotate check        # exit 1 if stale (CI)
sqlalchemy-annotate remove       # strip every block
sqlalchemy-annotate generate --dry-run     # show the diff, write nothing
```

`--models` points at the dotted package path. Subpackages are imported
recursively (`app/models/user.py`, `app/models/post.py`, ...), so every model
registers regardless of how many files you split them across. A broken or
circularly-importing module is reported as a warning and skipped, never fatal.

## Configuration

Put defaults in `pyproject.toml`; CLI flags override them.

```toml
[tool.sqlalchemy-annotate]
models = "app.models"
engine = "postgresql+asyncpg://..."   # dialect only, never connected
include_indexes = true
include_foreign_keys = true
include_relationships = false
normalize_types = false               # true -> Rails-style (bigint, varchar(255))
sort = "definition"                   # or "alphabetical"
position = "bottom"                   # or "top" to place the block above the class
exclude = ["audit_*", "*_history"]
```

### Type rendering

By default types are **truthful**: rendered exactly as SQLAlchemy compiles
them for the resolved dialect (`Mapped[int]` PK -> `integer`, `Mapped[str]` ->
`varchar`). Set `normalize_types = true` for Rails-style fabrication
(autoincrement int PK -> `bigint`, unlengthed string -> `varchar(255)`).

The dialect is `--dialect` if given, else the backend of `engine`
(async drivers collapse to their sync backend), else PostgreSQL.

## Alembic / pre-commit

Run it right after a schema change:

```bash
alembic revision --autogenerate -m "add users"
alembic upgrade head
sqlalchemy-annotate generate
```

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/abhinavs/sqlalchemy-annotate
    rev: v0.1.1
    hooks:
      - id: sqlalchemy-annotate
```

CI gate:

```yaml
- run: sqlalchemy-annotate check
```

## How it works

| Module | Responsibility |
|---|---|
| `discovery.py` | import-walk the package, collect mapped classes -> files |
| `schema.py`    | `Table`/`Mapper` -> `ModelSchema` value objects (pure) |
| `formatter.py` | `ModelSchema` -> comment lines (pure, pluggable renderer) |
| `parser.py`    | libcst helpers: build lines, locate the existing block |
| `writer.py`    | one libcst transformer: insert / replace / remove |
| `config.py`    | defaults <- pyproject.toml <- CLI |
| `cli.py`       | typer commands; heavy imports stay lazy |

## Roadmap (designed, not built)

The formatter is already a swappable `Renderer` behind the
`sqlalchemy_annotate.renderers` entry-point group, leaving room for: Markdown
schema export, ER diagram generation, a `schema diff` command, watch mode, and
an IDE/VSCode integration.

## Project

- [Contributing](CONTRIBUTING.md) - dev setup, the idempotency invariant, release steps
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md) - note: the tool imports your model package, like `pytest`/`alembic`
- Ships with [PEP 561](https://peps.python.org/pep-0561/) type information (`py.typed`)

## License

[MIT](LICENSE) (c) 2026 Abhinav Saxena
