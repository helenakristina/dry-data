# Dry Data — Project Guide for Claude Code

## Project overview

Dry Data is a data journalism web app that lets users explore alcohol-related trends
through interactive visualizations and natural language queries. Users ask questions
in plain English, the system translates them to SQL, runs them against a DuckDB
analytical database, and returns narrative answers with auto-generated charts.

**Not a health app.** This is a data exploration and journalism tool. It presents
publicly available population-level statistics. It does not collect user health data,
provide medical advice, track anyone's drinking, or make personalized health
recommendations.

## Tech stack

| Layer              | Technology         | Notes                                    |
|--------------------|--------------------|------------------------------------------|
| Language           | Python 3.11+       | Type hints everywhere, no `Any`          |
| Data processing    | Polars             | Prefer over pandas. Lazy evaluation.     |
| Database           | DuckDB             | Single-file analytical DB, star schema   |
| LLM                | OpenAI API (GPT-4o)| For NL→SQL and response generation       |
| MCP server         | mcp SDK (Python)   | Exposes DuckDB tools to the LLM          |
| Backend API        | FastAPI            | Async, Pydantic models for everything    |
| Frontend           | React + TypeScript | Vite, Tailwind CSS, Plotly for charts |
| Data formats       | Parquet            | Intermediate cleaned data files          |
| Testing            | pytest             | With polars testing utilities            |
| Linting            | ruff               | Format and lint in one tool              |

## Directory structure (monorepo)

```
dry-data/
├── CLAUDE.md                  # This file — project conventions
├── README.md                  # User-facing docs
├── .env.example               # Template for secrets (never commit .env)
│
├── backend/
│   ├── pyproject.toml         # Python deps, ruff, pytest config
│   ├── src/dry_data/          # Main Python package
│   │   ├── __init__.py
│   │   ├── config.py          # Settings via pydantic-settings
│   │   ├── exceptions.py      # Custom exception hierarchy
│   │   │
│   │   ├── ingest/            # Data download + raw storage
│   │   │   ├── base.py        # Abstract base class for ingestors
│   │   │   ├── brfss.py       # CDC BRFSS download + SAS→Parquet
│   │   │   ├── who.py         # WHO / Our World in Data CSVs
│   │   │   ├── fred.py        # FRED API for spending time series
│   │   │   └── trends.py      # Google Trends via pytrends
│   │   │
│   │   ├── transform/         # ETL: raw → cleaned → star schema
│   │   │   ├── base.py        # Abstract transformer
│   │   │   ├── brfss.py       # BRFSS cleaning + column mapping
│   │   │   ├── who.py         # Country name normalization
│   │   │   ├── fred.py        # Spending data alignment
│   │   │   ├── trends.py      # Trends normalization
│   │   │   └── dimensions.py  # Shared dimension tables
│   │   │
│   │   ├── warehouse/         # DuckDB schema + loading
│   │   │   ├── schema.py      # Star schema DDL
│   │   │   ├── loader.py      # Parquet → DuckDB loader
│   │   │   └── queries.py     # Pre-built analytical queries
│   │   │
│   │   ├── mcp_server/        # MCP server exposing data tools
│   │   │   ├── server.py      # Server setup + tool registration
│   │   │   └── tools.py       # Tool implementations
│   │   │
│   │   ├── llm/               # LLM integration layer
│   │   │   ├── client.py      # OpenAI client wrapper
│   │   │   ├── prompts.py     # System prompts, NL→SQL templates
│   │   │   └── chain.py       # question → SQL → narrative
│   │   │
│   │   └── api/               # FastAPI application
│   │       ├── app.py         # App factory
│   │       ├── routes/        # Route handlers
│   │       └── models.py      # Pydantic request/response models
│   │
│   ├── tests/                 # Python tests (pytest)
│   ├── scripts/               # CLI pipeline scripts
│   ├── notebooks/             # Exploration (not production)
│   └── data/                  # Raw + cleaned data (gitignored)
│       ├── raw/
│       ├── cleaned/
│       └── dry_data.duckdb
│
└── frontend/
    ├── package.json           # React + TypeScript + Vite + Tailwind
    ├── tsconfig.json
    ├── vite.config.ts         # Includes /api proxy to backend
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.tsx           # Entry point
        ├── App.tsx            # Shell with tab navigation
        ├── types/api.ts       # TS types matching backend Pydantic models
        ├── api/client.ts      # Typed fetch wrapper
        ├── components/
        │   ├── ChatInterface.tsx    # NL query chat UI
        │   ├── ChartRenderer.tsx    # Plotly-based chart from LLM spec
        │   └── DatasetBrowser.tsx   # Expandable dataset/column viewer
        ├── hooks/             # Custom React hooks
        └── lib/               # Utility functions
```

## Coding conventions

### Python style

- **Type hints on every function signature.** Use `str`, `int`, `float`, `bool`,
  `list[str]`, `dict[str, int]`, etc. Import from `collections.abc` for abstract
  types. Use `| None` not `Optional`.
- **Docstrings**: Google style. Required on all public functions and classes.
  One-liner for simple functions, multi-line with Args/Returns for complex ones.
- **No `print()` in library code.** Use `structlog` for logging. `print()` is
  fine in CLI scripts under `scripts/`.
- **Pydantic models** for all configuration, API request/response bodies, and
  data validation boundaries. Use `model_validator` for cross-field validation.
- **No bare `except`.** Always catch specific exceptions.
- **Constants** in SCREAMING_SNAKE_CASE at module level.
- **pathlib.Path** for all file paths, never string concatenation.
- **f-strings** for string formatting, never `.format()` or `%`.

### Polars conventions

- **Lazy by default.** Start chains with `.lazy()`, end with `.collect()` only
  when you need the result. This lets Polars optimize the query plan.
- **Use expressions, not loops.** `pl.col("x").mean()` not
  `df["x"].to_list()` then Python math.
- **Column naming**: snake_case, descriptive. `binge_drink_days_30d` not `ALCDAY5`.
  The transform layer maps source codes to readable names.
- **Schema declarations**: Define expected schemas as `dict[str, pl.DataType]`
  at the top of each transform module. Validate on read.

### DuckDB conventions

- **Star schema.** Fact tables hold measurements with foreign keys to dimension
  tables. Dimension tables hold descriptive attributes.
- **Table naming**: `fact_` prefix for fact tables, `dim_` prefix for dimensions.
  Example: `fact_brfss_responses`, `dim_state`, `dim_year`.
- **Column naming**: snake_case, matching the Polars output columns.
- **No views in production.** Materialized tables only. Views are fine for
  ad-hoc exploration in notebooks.
- **Parameterized queries only.** Never interpolate user input into SQL strings.
  Use DuckDB's `execute(sql, params)` with `?` placeholders.

### Testing conventions

- **One test file per source module.** `test_transform/test_brfss.py` tests
  `transform/brfss.py`.
- **Use fixtures for DuckDB.** Create a temporary in-memory DuckDB in
  `conftest.py` and populate with small sample data.
- **Test the transform layer thoroughly.** These are the most bug-prone parts.
  Test column mappings, null handling, type casting, edge cases.
- **Snapshot tests for SQL generation.** If the LLM generates SQL, snapshot the
  output for known questions and flag regressions.

### Frontend conventions (React + TypeScript)

- **Strict TypeScript.** `noUncheckedIndexedAccess` is on. No `any` types.
  Use the interfaces in `types/api.ts` for all API communication.
- **Functional components only.** No class components. Use hooks for state
  and effects.
- **Tailwind for styling.** No CSS modules, no styled-components, no inline
  style objects. Use Tailwind utility classes directly in JSX.
- **Component file naming**: PascalCase matching the export.
  `ChatInterface.tsx` exports `ChatInterface`.
- **Keep components focused.** If a component exceeds ~150 lines, extract
  sub-components or a custom hook.
- **Custom hooks** go in `frontend/src/hooks/` and are named `use*.ts`.
- **API types are the contract.** The TypeScript interfaces in `types/api.ts`
  must exactly mirror the Pydantic models in `backend/src/dry_data/api/models.py`.
  When one changes, update the other.
- **No `localStorage`** for state. Use React state. If persistence is needed
  later, discuss first.
- **Vite proxy**: In dev mode, `/api/*` requests proxy to `localhost:8001`.
  The API client uses relative paths (`/api/query`), never absolute URLs.
- **Plotly for all charts.** The `ChartRenderer` component takes a Plotly
  figure spec and renders it via `react-plotly.js`. The LLM generates the
  spec directly — no intermediate chart type mapping. This gives us hover,
  zoom, pan, export-to-PNG, and choropleth maps for free. Add layout
  customizations in `ChartRenderer`'s `BASE_LAYOUT`, not in individual
  components.

### Error handling

- **Custom exceptions** in `src/dry_data/exceptions.py`. At minimum:
  `IngestionError`, `TransformError`, `WarehouseError`, `QueryError`.
- **Fail fast on bad data.** If a downloaded file is corrupt or schema doesn't
  match, raise immediately with a clear message. Don't silently drop rows.
- **Retry with backoff** for network requests (downloads, API calls). Use
  `tenacity` library. Max 3 retries, exponential backoff.

### Git conventions

- **Conventional commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:`. Example: `feat(ingest): add BRFSS SAS transport file parser`.
- **Never commit**: `.env`, `data/raw/`, `data/cleaned/`, `*.duckdb`,
  `node_modules/`, `__pycache__/`, `.venv/`.
- **Always commit**: `data/.gitkeep` files, schema definitions, sample data
  for tests.

## Data pipeline flow

```
1. INGEST:   Download raw files → data/raw/{source}/
2. TRANSFORM: Raw files → cleaned Parquet → data/cleaned/{source}/
3. LOAD:     Parquet → DuckDB star schema → data/dry_data.duckdb
```

Each step is idempotent. Running it again overwrites the output cleanly.

## MCP server design

The MCP server exposes these tools to the LLM:

| Tool               | Description                                        |
|--------------------|----------------------------------------------------|
| `list_datasets`    | Returns available fact/dim tables with descriptions |
| `get_schema`       | Returns column names, types, sample values for a table |
| `query_data`       | Executes a read-only SQL query, returns results as JSON |
| `summarize_column` | Returns stats (min, max, mean, nulls, top values) for a column |

**Security**: The MCP server enforces read-only access. It rejects any SQL
containing `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, or `ATTACH`.
It also enforces a row limit (default 1000) on query results.

## LLM integration notes

- **Model**: GPT-4o via OpenAI API. Set via `OPENAI_MODEL` env var so it's
  swappable.
- **System prompt**: Lives in `src/dry_data/llm/prompts.py`. Tells the model
  it's a data analyst, gives it the schema, and instructs it to use the MCP
  tools to answer questions.
- **NL→SQL flow**: User question → LLM generates SQL using schema context →
  MCP server executes → LLM narrates the results with suggested chart type.
- **Chart output**: The LLM response includes a `chart` field containing a
  Plotly figure spec (`data` array + optional `layout` object). The frontend
  passes this directly to `react-plotly.js` — no mapping layer needed.
  This means the LLM can use any Plotly trace type: bar, scatter, line,
  choropleth, histogram, etc. The `ChartRenderer` component merges in a
  base layout for consistent styling.
- **Token budget**: Keep system prompts under 2000 tokens. Schema context is
  injected dynamically based on which tables the question seems to reference.

## Environment variables

```bash
# .env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
FRED_API_KEY=...              # Free from FRED website
DUCKDB_PATH=data/dry_data.duckdb
LOG_LEVEL=INFO
```

## Quick start (for Claude Code)

**TDD is non-negotiable for new code.** For every new function, endpoint, or
component: write a failing test FIRST, run it, confirm it fails because the
feature is missing, then write the minimum implementation to make it pass.
If you catch yourself writing implementation before the test, stop — delete
the implementation, write the test, watch it fail, then reimplement. Read
the `testing-discipline` skill in `.claude/skills/` for the full rules.

When starting work on this project:

1. Read the relevant skill(s) in `.claude/skills/` before writing any code
2. Check which phase we're in (ingest, transform, warehouse, mcp, llm, api, frontend)
3. Read the relevant module's docstrings and existing code
4. For backend work:
   - `cd backend`
   - Ensure venv is active (project uses `uv`, not pip/venv directly)
   - Run existing tests before changes: `uv run pytest tests/ -x -q`
   - After changes: `uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run pytest tests/ -x`
5. For frontend work:
   - `cd frontend`
   - `npm run typecheck` before and after changes
   - `npm run lint` to check style
   - `npx vitest run` to run tests
6. Keep functions small (< 40 lines). Extract helpers early.
7. When changing API models: update BOTH `backend/.../models.py` AND
   `frontend/src/types/api.ts` in the same commit.
   
## Package management

- **Backend**: Use `uv` for all Python dependency management. `uv venv` to
  create, `uv pip install` to install. Never use bare `pip` or `python -m venv`.
- **Frontend**: Use `npm` for Node dependencies. `npm install` to install,
  `npm run <script>` to run.

## What "done" looks like

A user visits the app, sees a few pre-built "story" visualizations (global
consumption trends, the sober-curious Google Trends curve, US spending over time),
and can type natural language questions like:

- "Which US states have the highest binge drinking rates?"
- "How has alcohol consumption changed in Scandinavian countries since 2000?"
- "What's the correlation between alcohol spending and income level?"
- "Show me the Google Trends data for 'sober curious' vs 'dry january'"

The app returns a narrative answer with an interactive chart.
