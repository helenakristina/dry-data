---
review_agents:
  - compound-engineering:review:kieran-python-reviewer
  - compound-engineering:review:kieran-typescript-reviewer
  - compound-engineering:review:security-sentinel
  - compound-engineering:review:performance-oracle
  - compound-engineering:review:architecture-strategist
  - compound-engineering:review:code-simplicity-reviewer
---

## Project Context for Review Agents

This is a Python + TypeScript monorepo called Dry Data — a data journalism web app for exploring alcohol-related trends.

**Stack:** Python 3.11, FastAPI, DuckDB (star schema), Polars, OpenAI API, tenacity, structlog, pytest / React 19, TypeScript, Vite, Tailwind, Plotly, Vitest, MSW.

**Architecture:** Layered backend (routes → services → repositories → providers). All DI via FastAPI Depends(). Domain exceptions (IngestionError, TransformError, WarehouseError, QueryError, LLMError) — never HTTPException outside routes. Read-only DuckDB in the API; write connection only in the pipeline script.

**What was implemented:** Full WHO/OWID alcohol data slice — ingest → transform → DuckDB load → repository layer → LLM NL→SQL service → FastAPI endpoints → React frontend with StoryChart landing page and Vitest test suite.

**Key files:**
- `backend/src/dry_data/` — Python package
- `backend/tests/` — pytest test suite (real in-memory DuckDB, no DB mocks)
- `frontend/src/` — React + TypeScript frontend
