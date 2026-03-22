# Dry Data — Backend

Python backend for the Dry Data data journalism platform.

## Quick start

```bash
uv sync
uv run uvicorn dry_data.api.app:app --port 8001 --reload
```

## Pipeline

```bash
uv run python -m scripts.run_pipeline
```

## Tests

```bash
uv run pytest tests/ -x -q
```
