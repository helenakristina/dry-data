# PRD: WHO/OWID Dataset — End-to-End First Slice

## Summary

Wire the first dataset (WHO alcohol consumption data via Our World in Data)
through every layer of the stack: ingest → transform → DuckDB warehouse →
MCP server → OpenAI NL→SQL → FastAPI API → React frontend with chat and a
pre-built animated line chart. This is one PR that proves the architecture
works end-to-end.

## Goals

1. A user can visit the app and see an animated line chart showing global
   alcohol consumption trends over decades.
2. A user can type a natural language question like "Which countries drink
   the most?" and get back a narrative answer with an auto-generated Plotly
   chart.
3. The full data pipeline (download → clean → load → query) is automated
   and idempotent.
4. The codebase follows all conventions in CLAUDE.md and the skills files.

## Non-Goals

- Other datasets (BRFSS, FRED, Google Trends) — future PRs.
- User authentication or accounts.
- Deployment or CI/CD.
- Dark mode.
- WHO GHO API direct integration (stretch goal, not required for this PR).

---

## Data Source

### Primary: Our World in Data (OWID)

OWID publishes clean CSVs derived from WHO Global Health Observatory data.
License: CC BY 4.0.

**Download URLs** (CSV format, append `?v=1&csvType=full&useColumnShortNames=false`):

| Indicator | URL |
|---|---|
| Total alcohol consumption per capita | `https://ourworldindata.org/grapher/total-alcohol-consumption-per-capita-litres-of-pure-alcohol` |
| Male vs female consumption | `https://ourworldindata.org/grapher/alcohol-consumption-per-capita-men-women` |
| Share of drinkers in population | `https://ourworldindata.org/grapher/share-of-adults-who-drink-alcohol` |

Each CSV has columns: `Entity`, `Code`, `Year`, and one or more value columns.
Data covers 190+ countries, years ~2000–2020.

**To get the actual CSV download URL**, append `.csv?v=1&csvType=full&useColumnShortNames=false`
to the grapher URL. For example:
`https://ourworldindata.org/grapher/total-alcohol-consumption-per-capita-litres-of-pure-alcohol.csv?v=1&csvType=full&useColumnShortNames=false`

### Stretch: WHO GHO API

If time permits, add a second ingestor that pulls the same data from the WHO
GHO API at `https://ghoapi.azureedge.net/api/`. This is not required for the
PR to be considered complete.

---

## Backend Work

### 1. Models (`backend/src/dry_data/models/`)

Create Pydantic models used across layers:

**`models/warehouse.py`:**
- `QueryResult` — columns (list[str]) + rows (list[list]) returned from DuckDB
- `TableSchema` — table_name, columns (list[ColumnInfo]), row_count
- `ColumnInfo` — name, type, nullable, sample_values

**`models/api.py`:**
- `QueryRequest` — question: str (min_length=1, max_length=500)
- `QueryResponse` — question, narrative, sql, chart (dict | None), error (str | None)
- `DatasetInfo` — table_name, description, row_count, columns
- `HealthResponse` — status: str

**`models/llm.py`:**
- `PlotlySpec` — data (list[dict]), layout (dict | None)

### 2. Ingestor (`backend/src/dry_data/ingest/who.py`)

Extend `BaseIngestor`. Source name: `"who"`.

**Behavior:**
- Download 3 CSV files from OWID URLs listed above using `httpx`.
- Save to `data/raw/who/` as `consumption.csv`, `consumption_by_sex.csv`,
  `share_drinkers.csv`.
- Validate each download: non-empty, contains expected header columns.
- Retry up to 3 times with exponential backoff via `tenacity`.
- Raise `IngestionError` on failure.
- Idempotent: re-running overwrites existing files.

**Test requirements:**
- Test successful download writes correct files (mock httpx).
- Test HTTP error raises `IngestionError`.
- Test empty response raises `IngestionError`.
- Test re-run doesn't create duplicate files.

### 3. Transformer (`backend/src/dry_data/transform/who.py`)

Extend `BaseTransformer`. Source name: `"who"`.

**Input:** 3 CSV files from `data/raw/who/`.

**Behavior:**
- Read each CSV with Polars.
- Rename columns: `Entity` → `country_name`, `Code` → `iso3`, `Year` → `year`,
  and value columns to descriptive snake_case names.
- Filter out aggregate rows (entries where `Entity` is a region/continent like
  "World", "Europe", "Africa", etc., or where `Code` is null/empty).
- Normalize country names where needed (e.g., "Turkiye" → "Turkey",
  "United States of America" → "United States"). Use a shared mapping dict
  in `transform/dimensions.py`.
- Validate: no nulls in `iso3` or `year` columns after filtering.
- Build dimension table contributions:
  - `dim_country` entries from unique country/iso3 pairs.
  - `dim_year` entries from unique years.
- Build fact table: `fact_global_consumption` with columns matching the DuckDB
  schema (see `warehouse/schema.py`). Include per-capita consumption, sex
  breakdown, and share of drinkers.
- Write all outputs as Parquet files via `self._write_parquet()`.
- Raise `TransformError` on schema mismatches or unexpected nulls.

**Test requirements:**
- Test column renaming produces expected output columns.
- Test aggregate/region rows are filtered out.
- Test Unicode country names survive normalization.
- Test nulls in required columns raise `TransformError`.
- Test output schema matches DuckDB warehouse schema.

### 4. Dimension builder (`backend/src/dry_data/transform/dimensions.py`)

Shared utility for building dimension tables:

- `normalize_country_name(name: str) -> str` — mapping dict for known variants.
- `build_dim_country(df: pl.DataFrame) -> pl.DataFrame` — deduplicated country
  dimension from any DataFrame with `country_name` and `iso3` columns.
- `build_dim_year(df: pl.DataFrame) -> pl.DataFrame` — deduplicated year
  dimension from any DataFrame with a `year` column.

These functions will be reused by future transformers (BRFSS, FRED, etc.).

### 5. Warehouse loader (`backend/src/dry_data/warehouse/loader_who.py`)

Each data source gets its own loader file. The shared schema lives in `schema.py`.

- `load_who_dimensions(con, cleaned_dir)` — loads `dim_country` and `dim_year`
  contributions from WHO Parquet files. Dimensions are additive (future sources
  will add more countries/years).
- `load_who_facts(con, cleaned_dir)` — loads `fact_global_consumption` from
  the WHO Parquet file. Truncate + insert for idempotency.
- `load_all_who(con, cleaned_dir)` — orchestrates: dimensions first, then facts.
- Validates Parquet columns match the target table before loading.
- Raises `WarehouseError` on schema mismatch or load failure.

Future sources get their own loaders: `loader_brfss.py`, `loader_fred.py`, etc.

**Test requirements:**
- Test successful load populates tables with correct row counts.
- Test schema mismatch raises `WarehouseError`.
- Test idempotent: loading twice doesn't double row count.

### 6. Repositories (`backend/src/dry_data/warehouse/`)

Each data source gets its own repository. Shared query logic lives in a base class.

**`warehouse/repository_base.py`** — `BaseDataRepository`:
- `__init__(self, con: duckdb.DuckDBPyConnection)`
- `execute_safe_query(sql, max_rows=1000) -> QueryResult` — validates SQL
  safety (rejects destructive keywords), executes, returns typed result.
- `get_table_schema(table_name) -> TableSchema` — DESCRIBE + sample values.
- `list_tables() -> list[DatasetInfo]` — all tables with descriptions and row counts.
- `_validate_sql(sql)` — shared SQL safety check.

**`warehouse/repository_who.py`** — `WHORepository(BaseDataRepository)`:
- `get_global_trend_chart() -> PlotlySpec` — canned query for the landing page
  story chart (global average + highlighted countries over time). Returns a
  pre-built Plotly spec, no LLM needed.
- `get_relevant_schema(question: str) -> str` — returns DDL for WHO-related
  tables when the question mentions countries, consumption, global, etc.

Future sources get their own repos: `repository_brfss.py`, `repository_fred.py`.
The `QueryService` receives the appropriate repository via DI.

**Test requirements:**
- Test destructive SQL is rejected (`DROP`, `DELETE`, etc.).
- Test row limit is enforced.
- Test `get_table_schema` returns correct column types.
- Test `list_tables` returns all tables with descriptions.
- Test `get_global_trend_chart` returns valid PlotlySpec with expected traces.

### 7. LLM provider (`backend/src/dry_data/llm/`)

**`llm/base.py`** — ABC with methods:
- `generate_sql(question, schema_context) -> str`
- `narrate_results(question, results) -> str`
- `suggest_chart(question, results) -> dict | None`

**`llm/openai_provider.py`** — Concrete implementation:
- Takes `AsyncOpenAI` client and model string in `__init__`.
- `generate_sql`: System prompt instructs the model to generate DuckDB-compatible
  SQL based on the provided schema. Strip markdown fences from response.
- `narrate_results`: System prompt instructs the model to write a clear,
  concise narrative explaining the query results in the context of the
  original question. Tone: informative data journalism, not clinical.
- `suggest_chart`: System prompt instructs the model to return a Plotly figure
  spec (JSON with `data` and `layout` keys) or null if no chart fits.
  The model should pick appropriate chart types (bar for rankings, line for
  trends, choropleth for geographic data).
- All methods use `tenacity` retry for transient OpenAI errors.
- Raises `LLMError` on persistent failures.

**`llm/prompts.py`** — System prompt templates:
- `SQL_SYSTEM_PROMPT` — role, schema context placeholder, DuckDB SQL dialect notes.
- `NARRATION_SYSTEM_PROMPT` — data journalist role, tone guidance.
- `CHART_SYSTEM_PROMPT` — Plotly spec format instructions, chart type selection.

**Test requirements:**
- Test prompt builder includes relevant schema, excludes irrelevant tables.
- Test markdown fence stripping (```sql blocks).
- Test handles empty/malformed LLM responses gracefully.
- Test rate limit error raises `LLMError` with user-friendly message.
- Mock `AsyncOpenAI` in all tests — never call the real API in tests.

### 8. Query service (`backend/src/dry_data/services/query_service.py`)

`QueryService` class:
- `__init__(self, data_repo: DataRepository, llm_provider: LLMProviderBase)`
- `answer_question(question: str) -> QueryResponse` — orchestrates the full
  NL→SQL→narrative→chart pipeline.
- Catches `QueryError` from repo (bad SQL) and retries with error context
  fed back to the LLM once before giving up.

**Test requirements:**
- Test end-to-end flow with mocked LLM and real in-memory DuckDB.
- Test LLM-generated bad SQL triggers one retry.
- Test persistent LLM failure returns error response, doesn't crash.

### 9. Dependencies (`backend/src/dry_data/api/dependencies.py`)

Factory functions wiring everything together:
- `get_db_connection()` → DuckDB connection (read-only)
- `get_base_data_repo()` → `BaseDataRepository` (generic queries, SQL validation)
- `get_who_repo()` → `WHORepository` (story chart, WHO-specific schema context)
- `get_llm_provider()` → `OpenAIProvider`
- `get_query_service()` → `QueryService` (receives base repo + LLM provider)

Future sources add their own factory functions (e.g., `get_brfss_repo()`).

### 10. FastAPI routes

**`api/routes/query.py`:**
- `POST /api/query` — accepts `QueryRequest`, returns `QueryResponse`.
  Injects `QueryService` via `Depends`. Catches domain exceptions → HTTP errors.

**`api/routes/datasets.py`:**
- `GET /api/datasets` — returns list of `DatasetInfo`. Injects `DataRepository`.

**`api/routes/health.py`:**
- `GET /api/health` — returns `{"status": "ok"}`.

**`api/app.py`:**
- App factory: `create_app()` registers all routers under `/api` prefix.

**Test requirements:**
- Test POST /api/query with empty question returns 422.
- Test POST /api/query with valid question returns 200 + QueryResponse shape.
- Test GET /api/datasets returns list of tables.
- Test GET /api/health returns 200.
- Use `httpx.AsyncClient` with the real FastAPI app, mock only OpenAI.

### 11. Pipeline script (`backend/scripts/run_pipeline.py`)

CLI script: `uv run -m scripts.run_pipeline`

Steps:
1. Run WHO ingestor (download CSVs).
2. Run WHO transformer (clean → Parquet).
3. Open DuckDB, create schema, load Parquet files.
4. Print summary: table names and row counts.

---

## Frontend Work

### 12. Vitest setup

Create `frontend/vitest.config.ts` and `frontend/src/test/setup.ts` as
specified in the frontend-development skill. Add vitest + @testing-library/react
+ msw to devDependencies. Add `"test": "vitest run"` to package.json scripts.

### 13. MSW mock handlers

Create `frontend/src/test/mocks/handlers.ts` with default handlers for
`/api/query`, `/api/datasets`, `/api/health`.

### 14. Landing page story visualization

Replace the empty-state starter cards in `ChatInterface` with a two-part
landing page:

**Top section:** An animated line chart showing global average alcohol
consumption per capita from 2000 to 2020. The chart should:
- Use Plotly with `type: "scatter"`, `mode: "lines"`.
- Animate on load (Plotly's `animation_frame` or a timed trace reveal).
- Show a few highlighted countries (e.g., World average, France, Russia,
  United States) as separate traces.
- Have a title: "Global alcohol consumption is declining — but not everywhere"
  (or similar data-driven headline; verify against actual data).

**Below the chart:** The existing starter question cards, now with 4 questions
relevant to the WHO data:
- "Which 10 countries have the highest alcohol consumption?"
- "How has alcohol consumption changed in Russia since 2000?"
- "What percentage of adults drink alcohol in the Middle East?"
- "Compare alcohol consumption between men and women globally"

This data should be fetched from a new backend endpoint:
`GET /api/story/global-trend` that returns a pre-built Plotly spec from a
canned DuckDB query (no LLM needed for the story chart).

### 15. Chat functionality

The existing `ChatInterface` component needs to be wired to the real API:
- `queryData()` from `api/client.ts` calls `POST /api/query`.
- Response narrative appears as an assistant message.
- If `chart` is non-null, `ChartRenderer` renders it inline.
- SQL is visible behind the disclosure toggle.
- Loading state shows "Querying the data..." with spinner.
- Error state shows a friendly message as an assistant message.

### 16. Dataset browser

Wire `DatasetBrowser` to `GET /api/datasets`. The component already handles
loading, error, and data states — it just needs the backend to return real data.

### 17. ChartRenderer empty state

Add a graceful empty state when `spec.data` is an empty array — show
"No data to visualize" instead of an empty Plotly chart.

### 18. Frontend tests

Write tests per the testing-discipline skill for:
- `ChatInterface`: send button disabled when empty, starter cards render,
  message appears after submit.
- `ChartRenderer`: renders without crashing on empty data, passes layout title.
- `DatasetBrowser`: shows loading state, handles empty dataset list.
- `api/client.ts`: throws `ApiError` on non-200 responses.

---

## Acceptance Criteria

- [ ] `uv run -m scripts.run_pipeline` downloads WHO data, transforms it,
      and loads it into DuckDB with no manual steps.
- [ ] `GET /api/datasets` returns table metadata for all WHO-related tables.
- [ ] `GET /api/health` returns 200.
- [ ] `POST /api/query` with "Which countries drink the most alcohol?"
      returns a narrative + Plotly bar chart spec.
- [ ] `POST /api/query` with "How has alcohol consumption changed in France?"
      returns a narrative + Plotly line chart spec.
- [ ] The landing page shows an animated line chart of global trends.
- [ ] Clicking a starter question sends it to the chat and shows a response.
- [ ] The dataset browser shows WHO tables with column details.
- [ ] `uv run pytest tests/ -x` passes with all tests green.
- [ ] `npm run typecheck && npx vitest run` passes in frontend/.
- [ ] `uv run ruff check src/ tests/` has no errors.
- [ ] No hardcoded OpenAI API keys anywhere — all via .env.
- [ ] README updated with the pipeline run command.

## Technical Notes

- **DuckDB schema** is already defined in `warehouse/schema.py`. The
  `fact_global_consumption` table and dimension tables are ready — don't
  modify the schema unless the OWID data truly doesn't fit.
- **Base classes** for ingestors and transformers are in `ingest/base.py`
  and `transform/base.py`. Extend them, don't rewrite.
- **Existing test fixtures** in `tests/conftest.py` provide an in-memory
  DuckDB with the schema created and sample dimension data. Use them.
- **The frontend proxy** is configured in `vite.config.ts` — `/api/*`
  requests go to `localhost:8000`. No CORS config needed in dev.
- **OpenAI model** is set via `OPENAI_MODEL` env var (default: `gpt-4o`).
  For cheaper testing during development, you can temporarily set it to
  `gpt-4o-mini`.
- **Follow the skills.** The `.claude/skills/` directory has three skills:
  `testing-discipline.md`, `backend-development.md`, `frontend-development.md`.
  Read them before starting. They define the DI pattern, testing rules,
  layer conventions, and frontend patterns.