---
title: "feat: WHO/OWID Dataset — End-to-End First Slice"
type: feat
status: active
date: 2026-03-21
---

# feat: WHO/OWID Dataset — End-to-End First Slice

## Overview

Wire the first dataset (WHO alcohol consumption via Our World in Data) through every layer of the stack: ingest → transform → DuckDB → MCP/repository → OpenAI NL→SQL → FastAPI → React frontend. This is the foundational PR that proves the full architecture works.

**Source:** `docs/planning/prd_who_data.md`

---

## Research Findings

### What Already Exists

| File | Status |
|---|---|
| `backend/src/dry_data/ingest/base.py` | ✅ `BaseIngestor` with `source_name`, `raw_dir`, `run()`, abstract `download()` |
| `backend/src/dry_data/transform/base.py` | ✅ `BaseTransformer` with `source_name`, `raw_dir`, `cleaned_dir`, `_write_parquet()`, `run()` |
| `backend/src/dry_data/warehouse/schema.py` | ✅ Full star schema DDL — `dim_country`, `dim_year`, `dim_beverage_type`, `fact_global_consumption` |
| `backend/src/dry_data/config.py` | ✅ Settings via `pydantic-settings` |
| `backend/src/dry_data/exceptions.py` | ✅ Custom exception hierarchy |
| `backend/tests/conftest.py` | ✅ `db`, `sample_dim_year`, `sample_dim_state` fixtures — **missing `dim_country` and `dim_beverage_type`** |
| `frontend/src/components/ChatInterface.tsx` | ✅ Full chat UI, 169 lines — needs landing page chart injected |
| `frontend/src/components/ChartRenderer.tsx` | ✅ Plotly wrapper with `BASE_LAYOUT` — **missing empty-state** |
| `frontend/src/components/DatasetBrowser.tsx` | ✅ Accordion browser — **missing `cancelled` flag pattern** |
| `frontend/src/api/client.ts` | ✅ `queryData`, `listDatasets`, `healthCheck` — **missing `getGlobalTrend()`** |
| `frontend/src/types/api.ts` | ✅ `QueryResponse`, `DatasetInfo`, etc. |
| `frontend/vite.config.ts` | ✅ Proxy `/api` → `http://localhost:8001` |

### What Does Not Exist Yet (All PRD Files)

Backend: `models/` package, `ingest/who.py`, `transform/who.py`, `transform/dimensions.py`, `warehouse/loader_who.py`, `warehouse/repository_base.py`, `warehouse/repository_who.py`, `llm/base.py`, `llm/openai_provider.py`, `llm/prompts.py`, `services/` package + `query_service.py`, `api/app.py`, `api/dependencies.py`, all route files, `scripts/run_pipeline.py`

Frontend: `vitest.config.ts`, `src/test/setup.ts`, `src/test/mocks/handlers.ts` — and none of the testing packages are installed.

### Pre-Work Gaps (Must Fix First)

1. **`pytest-httpx` missing** from `backend/pyproject.toml` devDependencies — required for mocking `httpx` in ingestor tests
2. **Frontend test stack missing** — `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `msw`, `jsdom` not in `package.json`
3. **`sample_dim_country` and `sample_dim_beverage_type` fixtures** missing from `tests/conftest.py` — needed for WHO fact table tests
4. **`services/` and `models/` directories** don't exist — create with `__init__.py`

### Key Technical Constraints

- **Backend port is 8001** (confirmed in `vite.config.ts` and `config.py`) — not 8000
- **`fact_global_consumption` has `sex VARCHAR(10)` and `beverage_type_id FK`** — the three OWID CSVs must be merged into rows keyed by (country, year, sex) with beverage_type = 'total' for all WHO data. See schema note below.
- **Surrogate key joins required in loader** — DuckDB loader must look up `country_id`, `year_id`, `beverage_type_id` from dimension tables after inserting dims, before inserting facts
- **`dim_country` has `continent` and `who_region`** — OWID only provides `Entity`/`Code`; these columns will be `NULL` until a future enrichment step
- **Read-only DuckDB in API** — `get_db_connection()` should open with `read_only=True`; the pipeline script uses a separate write connection

---

## Schema Note: Merging Three OWID CSVs

The `fact_global_consumption` fact table stores one row per (country, year, sex) combination:

| sex value | Source CSV | `liters_pure_alcohol_pc` | `pct_drinkers` |
|---|---|---|---|
| `'total'` | `consumption.csv` | ✅ | from `share_drinkers.csv` (joined by country+year) |
| `'male'` | `consumption_by_sex.csv` | ✅ | NULL |
| `'female'` | `consumption_by_sex.csv` | ✅ | NULL |

The transformer must join `share_drinkers.csv` onto the `'total'` rows by `(country_name, year)`. All rows get `beverage_type_id` pointing to a `'total'` row in `dim_beverage_type`.

---

## Proposed Solution

Build in six sequential phases. Each phase has passing tests before the next begins.

---

## Implementation Phases

> **TDD applies to all new code** (testing-discipline skill): write the test first, watch it fail for the right reason, then implement the minimum code to make it pass. For existing code being modified (e.g., `DatasetBrowser`, `ChartRenderer`), characterize current behavior first, then write a failing test for the new behavior before changing the code.

### Phase 1: Foundation — Models, Fixtures, Dev Dependencies

**Goal:** Shared Pydantic models, updated test fixtures, missing dev packages.

#### Tasks

- [ ] **`backend/pyproject.toml`** — add `pytest-httpx>=0.30` to `[tool.uv.dev-dependencies]`
- [ ] **`backend/src/dry_data/models/__init__.py`** — empty
- [ ] **`backend/src/dry_data/models/warehouse.py`** — `ColumnInfo`, `TableSchema`, `QueryResult`
- [ ] **`backend/src/dry_data/models/api.py`** — `QueryRequest`, `QueryResponse`, `DatasetInfo`, `HealthResponse`
- [ ] **`backend/src/dry_data/models/llm.py`** — `PlotlySpec`
- [ ] **`backend/tests/conftest.py`** — add `sample_dim_country` (seed 5 countries incl. France, Russia, USA, Germany, China) and `sample_dim_beverage_type` (seed `'total'` beverage) fixtures
- [ ] **`backend/tests/test_models/`** — basic smoke tests verifying model validation (e.g., `QueryRequest` rejects empty question)

#### Sample code

```python
# backend/src/dry_data/models/warehouse.py
class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    sample_values: list[str]

class TableSchema(BaseModel):
    table_name: str
    columns: list[ColumnInfo]
    row_count: int

class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list]  # list[list[Any]] via validator

# backend/src/dry_data/models/api.py
class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)

class QueryResponse(BaseModel):
    question: str
    narrative: str
    sql: str
    chart: dict | None
    error: str | None
```

---

### Phase 2: Data Pipeline — Ingest, Transform, Load

**Goal:** `uv run -m scripts.run_pipeline` downloads, cleans, and loads WHO data into DuckDB.

#### Tasks

- [ ] **`backend/src/dry_data/ingest/who.py`** — `WHOIngestor(BaseIngestor)`
  - `source_name = "who"`
  - Downloads 3 OWID CSVs using `httpx` (sync client), retries via `tenacity` (max 3, exponential)
  - Saves to `data/raw/who/consumption.csv`, `consumption_by_sex.csv`, `share_drinkers.csv`
  - Validates non-empty + expected headers; raises `IngestionError` on failure
- [ ] **`backend/src/dry_data/transform/dimensions.py`** — shared utilities
  - `COUNTRY_NAME_OVERRIDES: dict[str, str]` mapping ("Turkiye" → "Turkey", etc.)
  - `normalize_country_name(name: str) -> str`
  - `build_dim_country(df: pl.DataFrame) -> pl.DataFrame`
  - `build_dim_year(df: pl.DataFrame) -> pl.DataFrame`
- [ ] **`backend/src/dry_data/transform/who.py`** — `WHOTransformer(BaseTransformer)`
  - `source_name = "who"`
  - Reads 3 CSVs with Polars lazy evaluation
  - Renames columns: `Entity→country_name`, `Code→iso3`, `Year→year`
  - Filters aggregate rows (null/empty `iso3` or known region names)
  - Normalizes country names via `dimensions.py`
  - Merges 3 CSVs into `fact_global_consumption` format (see schema note above)
  - Builds `dim_country.parquet` and `dim_year.parquet` contributions
  - Writes `fact_global_consumption.parquet`, `dim_country.parquet`, `dim_year.parquet`
- [ ] **`backend/src/dry_data/warehouse/loader_who.py`**
  - `load_who_dimensions(con, cleaned_dir: Path)` — upsert dim_country + dim_year (INSERT OR IGNORE by unique key)
  - `load_who_facts(con, cleaned_dir: Path)` — TRUNCATE + INSERT fact_global_consumption; joins surrogate keys from dim tables
  - `load_all_who(con, cleaned_dir: Path)` — dims first, then facts; validates Parquet columns match table before loading
  - Raises `WarehouseError` on schema mismatch
- [ ] **`backend/scripts/__init__.py`** — empty (makes `scripts` importable)
- [ ] **`backend/scripts/run_pipeline.py`** — CLI via `typer`:
  1. `WHOIngestor().run()`
  2. `WHOTransformer().run()`
  3. Open DuckDB write connection, `create_all_tables()`, `load_all_who()`
  4. Print table names + row counts via `rich`

#### Test files

- `backend/tests/test_ingest/test_who.py` — uses `pytest-httpx` to mock OWID HTTP responses
- `backend/tests/test_transform/test_dimensions.py`
- `backend/tests/test_transform/test_who.py` — uses real Polars DataFrames (no mocks)
- `backend/tests/test_warehouse/test_loader_who.py` — uses in-memory DuckDB from conftest

#### Aggregate row filter list

Known OWID non-country entities to filter (incomplete — use `iso3 IS NULL OR iso3 = ''` as primary filter, supplement with name list for edge cases):
`"World"`, `"Africa"`, `"Asia"`, `"Europe"`, `"North America"`, `"South America"`, `"Oceania"`, `"High-income countries"`, `"Low-income countries"`, `"Upper-middle-income countries"`, `"Lower-middle-income countries"`

---

### Phase 3: Query Layer — Repository, LLM, Service

**Goal:** `QueryService.answer_question()` produces `QueryResponse` from a natural language question.

#### Tasks

- [ ] **`backend/src/dry_data/warehouse/repository_base.py`** — `BaseDataRepository`
  - `__init__(self, con: duckdb.DuckDBPyConnection)`
  - `_validate_sql(sql: str)` — rejects `INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|EXPORT|IMPORT` (case-insensitive, per backend-development skill)
  - `execute_safe_query(sql: str, max_rows: int = 1000) -> QueryResult`
  - `get_table_schema(table_name: str) -> TableSchema`
  - `list_tables() -> list[DatasetInfo]` — uses `get_table_descriptions()` from `schema.py`
- [ ] **`backend/src/dry_data/warehouse/repository_who.py`** — `WHORepository(BaseDataRepository)`
  - `get_global_trend_chart() -> PlotlySpec` — canned DuckDB query: global average + France, Russia, USA per year; returns Plotly `scatter` spec with `mode: "lines"`
  - `get_relevant_schema(question: str) -> str` — returns DDL for `fact_global_consumption`, `dim_country`, `dim_year` when question mentions countries, consumption, etc.
- [ ] **`backend/src/dry_data/llm/base.py`** — `LLMProviderBase` ABC
  - `generate_sql(question: str, schema_context: str) -> str`
  - `narrate_results(question: str, results: QueryResult) -> str`
  - `suggest_chart(question: str, results: QueryResult) -> dict | None`
- [ ] **`backend/src/dry_data/llm/prompts.py`** — system prompt constants
  - `SQL_SYSTEM_PROMPT` — DuckDB SQL dialect, schema context placeholder, read-only enforcement
  - `NARRATION_SYSTEM_PROMPT` — data journalist tone, concise, no hedging
  - `CHART_SYSTEM_PROMPT` — Plotly JSON spec format, chart type selection guide (bar→rankings, line→trends, choropleth→geographic)
- [ ] **`backend/src/dry_data/llm/openai_provider.py`** — `OpenAIProvider(LLMProviderBase)`
  - Takes `AsyncOpenAI` + model string
  - `generate_sql`: strips markdown fences (` ```sql ... ``` `)
  - `narrate_results`: formats `QueryResult` rows as a compact table string for the prompt
  - `suggest_chart`: parses JSON from response; returns `None` if response is `"null"` or malformed
  - All methods wrapped in `@retry(stop=stop_after_attempt(3), wait=wait_exponential())` from tenacity
  - Raises `LLMError` on persistent failure
- [ ] **`backend/src/dry_data/services/__init__.py`** — empty
- [ ] **`backend/src/dry_data/services/query_service.py`** — `QueryService`
  - `__init__(self, data_repo: BaseDataRepository, llm_provider: LLMProviderBase)`
  - `answer_question(question: str) -> QueryResponse`
    1. `llm.generate_sql(question, repo.get_relevant_schema(question))`
    2. `repo.execute_safe_query(sql)` — on `QueryError`, retry once with error context appended to prompt
    3. `llm.narrate_results(question, results)`
    4. `llm.suggest_chart(question, results)`
    5. Return `QueryResponse`

#### Test files

- `backend/tests/test_warehouse/test_repository_base.py`
- `backend/tests/test_warehouse/test_repository_who.py`
- `backend/tests/test_llm/test_openai_provider.py` — mock `AsyncOpenAI` entirely; never call real API
- `backend/tests/test_services/test_query_service.py` — real in-memory DuckDB + mocked LLM

---

### Phase 4: FastAPI API

**Goal:** All three endpoints respond correctly; integration tests pass with `httpx.AsyncClient`.

#### Tasks

- [ ] **`backend/src/dry_data/api/dependencies.py`**
  - `get_db_connection()` → `duckdb.connect(settings.duckdb_path, read_only=True)` as generator (yields + closes)
  - `get_base_data_repo(con=Depends(get_db_connection))` → `BaseDataRepository(con)`
  - `get_who_repo(con=Depends(get_db_connection))` → `WHORepository(con)`
  - `get_llm_provider()` → `OpenAIProvider(AsyncOpenAI(), settings.openai_model)`
  - `get_query_service(repo=Depends(get_base_data_repo), llm=Depends(get_llm_provider))` → `QueryService(repo, llm)`
- [ ] **`backend/src/dry_data/api/routes/health.py`** — `GET /health` → `{"status": "ok"}`
- [ ] **`backend/src/dry_data/api/routes/datasets.py`** — `GET /datasets` → `list[DatasetInfo]`
- [ ] **`backend/src/dry_data/api/routes/query.py`** — `POST /query` → `QueryResponse`; catches domain exceptions → appropriate HTTP status codes
- [ ] **`backend/src/dry_data/api/routes/story.py`** — `GET /story/global-trend` → `PlotlySpec` from `WHORepository.get_global_trend_chart()`
- [ ] **`backend/src/dry_data/api/app.py`** — `create_app()` factory:
  - Mounts all routers under `/api` prefix
  - Adds CORS middleware for dev (allow `localhost:3000`)
  - Returns configured `FastAPI` instance
- [ ] **`backend/src/dry_data/api/__init__.py`** — expose `create_app`

#### Exception→HTTP mapping

Per `backend-development` skill — routes catch domain exceptions and convert, never raise `HTTPException` in services or repos:

| Domain exception | HTTP status |
|---|---|
| `QueryError` (bad SQL or unsafe query) | 400 Bad Request |
| `LLMError` | 502 Bad Gateway |
| `WarehouseError` | 500 Internal Server Error |

#### Test files

- `backend/tests/test_api/test_routes.py` — uses `httpx.AsyncClient(app=create_app(), base_url="http://test")` with pytest-asyncio; mocks `get_llm_provider` dependency; uses real in-memory DuckDB (override `get_db_connection`)

---

### Phase 5: Frontend Test Infrastructure

**Goal:** `npm run typecheck && npx vitest run` passes with the test stack installed.

#### Tasks

- [ ] **`frontend/package.json`** — add devDependencies:
  ```json
  "vitest": "^1.0.0",
  "@vitest/ui": "^1.0.0",
  "@testing-library/react": "^14.0.0",
  "@testing-library/jest-dom": "^6.0.0",
  "@testing-library/user-event": "^14.0.0",
  "msw": "^2.0.0",
  "jsdom": "^24.0.0"
  ```
  Add `"test": "vitest run"` to `scripts`.
- [ ] **`frontend/vitest.config.ts`** (exact shape from frontend-development skill):
  ```ts
  import { defineConfig } from "vitest/config";
  import react from "@vitejs/plugin-react";
  import path from "path";

  export default defineConfig({
    plugins: [react()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: false,
    },
  });
  ```
- [ ] **`frontend/src/test/setup.ts`**:
  ```ts
  import "@testing-library/jest-dom/vitest";
  import { cleanup } from "@testing-library/react";
  import { afterEach } from "vitest";

  afterEach(() => { cleanup(); });
  ```
- [ ] **`frontend/src/test/mocks/handlers.ts`** — MSW handlers for `POST /api/query`, `GET /api/datasets`, `GET /api/health`, `GET /api/story/global-trend`
- [ ] **`frontend/src/test/mocks/server.ts`** — `setupServer(...handlers)`; `beforeAll`/`afterEach`/`afterAll` lifecycle

---

### Phase 6: Frontend Features

**Goal:** Landing page story chart, wired chat, dataset browser with real data, all frontend tests green.

#### Tasks

- [ ] **`frontend/src/api/client.ts`** — add `getGlobalTrend(): Promise<PlotlySpec>` calling `GET /api/story/global-trend`
- [ ] **`frontend/src/types/api.ts`** — verify all interfaces match backend Pydantic models exactly (should already match; confirm `PlotlySpec` shape)
- [ ] **`frontend/src/components/ChartRenderer.tsx`** — add empty-state: if `spec.data.length === 0`, render `<p>No data to visualize</p>` instead of Plotly; wrap rendered chart in `<div role="img" aria-label="...">` per frontend-development skill accessibility rules
- [ ] **`frontend/src/components/DatasetBrowser.tsx`** — add `cancelled` flag to `useEffect` per frontend-development skill:
  ```ts
  useEffect(() => {
    let cancelled = false
    listDatasets().then(data => { if (!cancelled) setDatasets(data) }).catch(...)
    return () => { cancelled = true }
  }, [])
  ```
- [ ] **`frontend/src/components/ChatInterface.tsx`** — replace empty state with two-part landing page:
  1. `<StoryChart />` sub-component (extract to `frontend/src/components/StoryChart.tsx`) — fetches `getGlobalTrend()`, renders via `ChartRenderer` with loading/error states and `cancelled` pattern
  2. Updated `STARTER_QUESTIONS` for WHO data (as specified in PRD §14)
- [ ] **`frontend/src/components/StoryChart.tsx`** — new component (extracted from ChatInterface landing):
  - Fetches `getGlobalTrend()` on mount with `cancelled` flag
  - Loading: skeleton or "Loading chart…" text
  - Error: silent (don't break landing page for story chart failure)
  - Success: `<ChartRenderer spec={data} />`

#### Test files

Co-located with source files per frontend-development skill (not in `__tests__/`):

- `frontend/src/components/ChatInterface.test.tsx`
- `frontend/src/components/ChartRenderer.test.tsx`
- `frontend/src/components/DatasetBrowser.test.tsx`
- `frontend/src/api/client.test.ts`

---

## Acceptance Criteria

### Pipeline
- [ ] `uv run -m scripts.run_pipeline` completes with no errors; prints table names + row counts
- [ ] Re-running is idempotent (row counts stay the same)

### API
- [ ] `GET /api/health` → 200 `{"status": "ok"}`
- [ ] `GET /api/datasets` → 200, list includes `fact_global_consumption`
- [ ] `POST /api/query` `{"question": "Which countries drink the most alcohol?"}` → 200, `narrative` non-empty, `chart.data` non-empty (bar chart)
- [ ] `POST /api/query` `{"question": "How has alcohol consumption changed in France?"}` → 200, line chart spec
- [ ] `POST /api/query` `{"question": ""}` → 422
- [ ] `GET /api/story/global-trend` → 200, valid Plotly spec with multiple traces

### Frontend
- [ ] Landing page shows animated line chart of global alcohol trends
- [ ] Clicking a starter question sends it to chat and shows response + chart inline
- [ ] Dataset browser shows WHO tables with columns
- [ ] `ChartRenderer` with `spec.data = []` shows "No data to visualize"

### Quality
- [ ] `cd backend && uv run pytest tests/ -x -q` — all green
- [ ] `cd frontend && npm run typecheck` — no errors
- [ ] `cd frontend && npx vitest run` — all green
- [ ] `cd backend && uv run ruff check src/ tests/` — no errors
- [ ] No `.env` file committed; no hardcoded API keys
- [ ] `README.md` updated with pipeline run command

---

## System-Wide Impact

### Interaction Graph

`POST /api/query` → `QueryService.answer_question()` → `LLMProvider.generate_sql()` (OpenAI API call, ~1-3s) → `BaseDataRepository.execute_safe_query()` (DuckDB read, <100ms) → on `QueryError`: retry with `LLMProvider.generate_sql()` again (adds error to prompt) → `LLMProvider.narrate_results()` (OpenAI, ~1-2s) → `LLMProvider.suggest_chart()` (OpenAI, ~1s) → `QueryResponse` returned.

`GET /api/story/global-trend` → `WHORepository.get_global_trend_chart()` → single DuckDB read → Plotly spec; no LLM involved.

### Error Propagation

- `httpx.HTTPError` in ingestor → wrapped as `IngestionError` (script only, not in API path)
- `QueryError` from `execute_safe_query` → caught in `QueryService`, fed back to LLM for one retry → on second failure, `QueryResponse(error=..., chart=None)` returned (HTTP 200 with error field, not a 4xx)
- `LLMError` (persistent OpenAI failure after tenacity retries) → route layer catches → HTTP 502
- `WarehouseError` (schema mismatch on load) → script aborts with structlog error, not in API path

### State Lifecycle Risks

- **Loader idempotency:** `load_who_facts` does TRUNCATE + INSERT — if the process dies mid-insert, the fact table will be empty (not half-loaded). DuckDB's ACID guarantees this is safe with a `BEGIN`/`COMMIT` block.
- **Dimension upsert:** `dim_country` uses INSERT OR IGNORE (by `iso3` uniqueness). Future sources adding the same country will not duplicate. Countries not in WHO data (e.g., territories without ISO codes) are filtered out in the transformer — no orphaned FK refs.
- **DuckDB read-only in API:** API opens DuckDB `read_only=True` — concurrent reads are safe. The pipeline script must not run while the API is serving (or use a copy of the DB file).

### API Surface Parity

The `GET /api/story/global-trend` endpoint returns a `PlotlySpec`. The `PlotlySpec` type is also used in `QueryResponse.chart`. Ensure both the route and the type definition use the same `models/llm.py:PlotlySpec` model — no inline dicts.

### Integration Test Scenarios

1. **Full query flow (real DuckDB, mocked OpenAI):** Seed in-memory DuckDB with WHO data → `POST /api/query` → verify `narrative` non-empty and `chart.data` is a list of dicts. *Unit tests with mocked repo wouldn't catch type mismatches between QueryResult and the Plotly prompt.*
2. **Bad SQL retry:** Mock LLM to return invalid SQL on first call, valid SQL on second → verify `QueryService` retried and returned a success response. *Tests that the retry mechanism actually passes error context back.*
3. **Row limit enforcement:** Seed fact table with 2000 rows → `execute_safe_query` → verify only 1000 rows returned and no exception raised.
4. **Empty OWID response:** Mock httpx to return a CSV with headers but no data rows → verify `WHOTransformer` raises `TransformError` (no rows after filtering).
5. **Surrogate key join:** Load dim_country with known country, load fact rows referencing it by `iso3` → verify `country_id` FK is correctly resolved and no NULL FKs in fact table.

---

## Dependencies & Prerequisites

- OpenAI API key in `.env` (`OPENAI_API_KEY`)
- FRED API key not needed for this PR
- DuckDB file at `data/dry_data.duckdb` (created by pipeline script)
- Backend running on port 8001 (`uv run uvicorn dry_data.api.app:app --port 8001 --reload`)
- Frontend dev server on port 3000 (`npm run dev`)

---

## Risk Analysis

| Risk | Likelihood | Mitigation |
|---|---|---|
| OWID CSV URL changes or returns non-CSV | Low | Validate content-type + headers in ingestor; `IngestionError` with clear message |
| `fact_global_consumption` schema doesn't fit 3 CSVs cleanly | Medium | Schema note above defines the merge strategy; add integration test for surrogate key resolution |
| LLM generates DuckDB-incompatible SQL | High | One retry with error context; test with `gpt-4o-mini` to catch prompt issues cheaply |
| OpenAI latency makes `POST /api/query` feel slow | High | Expected 3-7s total; add loading state in frontend (already exists in `ChatInterface`) |
| `dim_country.continent`/`who_region` NULL in joins | Medium | Explicitly allow NULLs in schema, document in `get_table_descriptions()` so LLM knows |

---

## Documentation Plan

- [ ] Update `README.md` with: setup steps, pipeline command (`uv run -m scripts.run_pipeline`), how to start backend + frontend, example questions
- [ ] Update `backend/pyproject.toml` `readme` field (currently broken — either create `backend/README.md` or remove the field)

---

## Sources & References

### Internal

- PRD: `docs/planning/prd_who_data.md`
- Base classes: `backend/src/dry_data/ingest/base.py`, `backend/src/dry_data/transform/base.py`
- Schema: `backend/src/dry_data/warehouse/schema.py`
- Test fixtures: `backend/tests/conftest.py`
- Frontend components: `frontend/src/components/ChatInterface.tsx:1`, `frontend/src/components/ChartRenderer.tsx:1`
- Vite proxy config: `frontend/vite.config.ts` (port 8001)
- Skills: `.claude/skills/backend-development/SKILL.md`, `.claude/skills/frontend-development/SKILL.md`, `.claude/skills/testing-discipline/SKILL.md`

### External

- OWID CSV endpoint pattern: `https://ourworldindata.org/grapher/<slug>.csv?v=1&csvType=full&useColumnShortNames=false`
- DuckDB Python docs: https://duckdb.org/docs/api/python/overview
- Plotly figure reference: https://plotly.com/python/figure-factories/
- MSW v2 docs: https://mswjs.io/docs/getting-started
