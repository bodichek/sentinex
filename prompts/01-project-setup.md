# Prompt 01: Project Setup

## Goal

Create the Sentinex Django project foundation with Poetry, initial structure, Docker Compose for local development, and CI configuration.

## Prerequisites

- Empty GitHub repo `sentinex` (privátní)
- Python 3.12 installed
- Poetry installed
- Docker and Docker Compose installed

## Context

This is the first step. We're creating the skeleton of a Django 5.1 project with a specific structure defined in `docs/ARCHITECTURE.md`. The project will grow to include multi-tenancy, agents, addons, but this step is about the bones.

Read `CLAUDE.md` and `docs/DEVELOPMENT.md` before starting.

## Constraints

- Python 3.12 only (specify in `pyproject.toml`)
- Django 5.1
- Poetry for dependency management
- Folder structure per `docs/ARCHITECTURE.md`
- Ruff for lint/format
- mypy strict mode
- pytest + pytest-django for testing

## Deliverables

After this prompt, the repo should have:

1. `pyproject.toml` with Poetry config and initial dependencies
2. `poetry.lock` committed
3. Django project at repo root named `config/` (settings module)
4. `apps/` directory with placeholder for `core/`, `agents/`, `data_access/`, `addons/`
5. `docker-compose.yml` for local development (postgres, redis)
6. `docker-compose.prod.yml` for production (web containers, nginx)
7. `Dockerfile` for the application
8. `.env.example` with all required variables documented
9. `.gitignore` with Python, Django, secrets patterns
10. `.github/workflows/ci.yml` — run tests, lint, type check on PR
11. `manage.py`
12. Basic `config/settings/base.py`, `dev.py`, `prod.py`, `test.py`
13. Empty `tests/` directory at root with `conftest.py`
14. README.md at root (copy from docs/ or from prepared content)
15. CLAUDE.md at root (copy from prepared content)

## Acceptance Criteria

- `poetry install` succeeds
- `docker-compose up -d postgres redis` starts services
- `poetry run python manage.py check` passes (no Django errors)
- `poetry run pytest` passes (no tests yet, but framework works)
- `poetry run ruff check .` passes
- `poetry run mypy .` passes
- CI workflow triggers on PR (tested by opening draft PR)
- Repo is importable: cloning + `poetry install` works for new dev

## Next Steps

After this prompt, proceed to `02-django-tenancy.md`.

## Notes for Claude Code

- Create `apps/` with `__init__.py` and placeholder subdirs, but no content yet
- Settings should use `django-environ` for env variable handling
- Dockerfile should use multi-stage build (builder stage + runtime stage)
- docker-compose should have health checks for postgres and redis
- Use `uv` in Dockerfile for faster installs (Poetry for local dev is fine)
- pyproject.toml includes ruff and mypy configurations
- Line length: 100 characters
- Include initial `.pre-commit-config.yaml` (optional but recommended)
