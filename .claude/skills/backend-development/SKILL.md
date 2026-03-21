---
name: backend-development
description: >
  Use when writing, modifying, or reviewing any Python code in the backend/ directory.
  Enforces this project's architectural patterns: dependency injection via FastAPI
  Depends(), layered architecture (routes → services → repositories → providers),
  domain exceptions, Polars-first data handling, DuckDB star schema, and MCP server
  patterns. Always use alongside the testing-discipline skill.
version: 1.0.0
languages: [python]
---

# Backend Development — Dry Data

## Before You Write Any Code

1. Read `CLAUDE.md` at the project root for conventions.
2. Read the `testing-discipline` skill. Apply TDD for new code.
3. Identify which layer you're working in.
4. Run existing tests: `cd backend && uv run pytest tests/ -x -q`

---

## Architecture Overview

```
Routes (thin)  →  Services (orchestration + business logic)  →  Repositories (data access)
                       ↓
                  Providers (external APIs via ABC)
                       ↓
                  Utils (pure functions, no side effects)
```

Every layer has one job. Don't mix them.

### The Data Pipeline Has Its Own Flow

```
Ingest (download raw) → Transform (clean with Polars) → Warehouse (load to DuckDB)
                                                              ↓
                                              MCP Server (expose tools)
                                                              ↓
                                              LLM Layer (NL→SQL via OpenAI)
                                                              ↓
                                              FastAPI Routes (serve to frontend)
```

The pipeline layers (ingest, transform, warehouse) follow the base class pattern.
The API layers (routes, services, repos, providers) follow the DI pattern below.

---

## Layer Rules

### Routes — Thin & Focused

Routes do orchestration only. 20-40 lines maximum.

**Routes MUST:**

- Accept request, call services, return response
- Validate input via Pydantic models
- Inject all dependencies via FastAPI `Depends()`
- Return proper status codes (201 create, 204 delete, 422 validation)
- Catch domain exceptions and convert to HTTPException

**Routes MUST NOT:**

- Contain business logic
- Access DuckDB directly (that's the repository's job)
- Instantiate services or providers (that's `dependencies.py`)
- Exceed 40 lines

```python
from fastapi import APIRouter, Depends, HTTPException

from dry_data.api.dependencies import get_query_service
from dry_data.models.api import QueryRequest, QueryResponse
from dry_data.services.query_service import QueryService
from dry_data.exceptions import QueryError, LLMError

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
async def query_data(
    request: QueryRequest,
    query_service: QueryService = Depends(get_query_service),
) -> QueryResponse:
    """Answer a natural language question about alcohol trends."""
    try:
        return await query_service.answer_question(request.question)
    except QueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LLMError:
        raise HTTPException(
            status_code=502,
            detail="Unable to process your question right now. Try rephrasing.",
        )
```

### Services — Business Logic & Orchestration

Services contain business logic. They call repositories and providers but never
access DuckDB or external APIs directly.

**Services MUST:**

- Take dependencies in `__init__` (never create them)
- Use injected providers for external API calls (OpenAI)
- Use injected repositories for data access (DuckDB)
- Contain business logic, prompt building, response shaping
- Have complete type hints and docstrings

**Services MUST NOT:**

- Import or instantiate `openai.OpenAI`, `duckdb.connect()`, or any concrete client
- Raise `HTTPException` (that's the route's job — raise domain exceptions)
- Access `settings` directly for API keys (receive via DI)

```python
class QueryService:
    """Orchestrates NL question → SQL → narrative response."""

    def __init__(
        self,
        data_repo: DataRepository,
        llm_provider: LLMProviderBase,
    ) -> None:
        self._data_repo = data_repo
        self._llm = llm_provider

    async def answer_question(self, question: str) -> QueryResponse:
        schema_context = self._data_repo.get_relevant_schema(question)
        sql = await self._llm.generate_sql(question, schema_context)
        results = self._data_repo.execute_safe_query(sql)
        narrative = await self._llm.narrate_results(question, results)
        chart = await self._llm.suggest_chart(question, results)
        return QueryResponse(
            question=question,
            narrative=narrative,
            sql=sql,
            chart=chart,
        )
```

### Repositories — Data Access Only

Repositories handle all DuckDB queries. Nothing else touches the database.

**Repositories MUST:**

- Take a DuckDB connection in `__init__`
- Return typed Pydantic models or typed dicts (never raw tuples)
- Raise `QueryError` when queries fail or are unsafe
- Raise `WarehouseError` when schema/loading operations fail
- Use parameterized queries (never string interpolation)
- Re-raise specific exceptions before the generic `except` catches them

**Repositories MUST NOT:**

- Raise `HTTPException` (domain exceptions only)
- Contain business logic
- Call external APIs

```python
class DataRepository:
    """Read-only access to the Dry Data DuckDB warehouse."""

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    def execute_safe_query(self, sql: str, max_rows: int = 1000) -> QueryResult:
        """Execute a validated read-only SQL query."""
        self._validate_sql(sql)
        try:
            result = self._con.execute(sql).fetchmany(max_rows)
            columns = [desc[0] for desc in self._con.description]
            return QueryResult(columns=columns, rows=result)
        except QueryError:
            raise  # Don't let the generic handler swallow domain exceptions
        except duckdb.Error as exc:
            raise QueryError(f"Query execution failed: {exc}") from exc

    def _validate_sql(self, sql: str) -> None:
        """Reject destructive SQL statements."""
        forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
                     "ALTER", "ATTACH", "COPY", "EXPORT", "IMPORT"}
        tokens = sql.upper().split()
        if forbidden & set(tokens):
            raise QueryError("Prohibited SQL operation detected")

    def get_table_schema(self, table_name: str) -> TableSchema:
        """Return column info for a table."""
        try:
            cols = self._con.execute(f"DESCRIBE {table_name}").fetchall()
            return TableSchema(
                table_name=table_name,
                columns=[
                    ColumnInfo(name=c[0], type=c[1], nullable=c[2] == "YES")
                    for c in cols
                ],
            )
        except duckdb.CatalogException as exc:
            raise QueryError(f"Table not found: {table_name}") from exc
```

### Providers — External API Abstraction

Providers wrap external services (OpenAI, future Anthropic, etc.) behind ABCs.

**The three-file pattern is mandatory for all external API integrations:**

| File                     | Purpose                                             |
| ------------------------ | --------------------------------------------------- |
| `llm/base.py`            | ABC defining the interface contract                 |
| `llm/openai_provider.py` | Concrete implementation with real OpenAI calls      |
| `llm/prompts.py`         | System prompts, templates (shared across providers) |

The service never knows which provider it's using. Swapping OpenAI for
Anthropic means changing one line in `dependencies.py`.

```python
# llm/base.py — the contract
import abc

class LLMProviderBase(abc.ABC):
    """Interface for LLM providers (OpenAI, Anthropic, local, etc.)."""

    @abc.abstractmethod
    async def generate_sql(self, question: str, schema_context: str) -> str:
        """Translate a natural language question into SQL."""

    @abc.abstractmethod
    async def narrate_results(self, question: str, results: QueryResult) -> str:
        """Generate a narrative explanation of query results."""

    @abc.abstractmethod
    async def suggest_chart(
        self, question: str, results: QueryResult,
    ) -> dict | None:
        """Return a Plotly figure spec or None if no chart fits."""
```

````python
# llm/openai_provider.py — concrete implementation
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from dry_data.llm.base import LLMProviderBase

class OpenAIProvider(LLMProviderBase):
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def generate_sql(self, question: str, schema_context: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[...],
        )
        return self._strip_markdown_fences(response.choices[0].message.content)

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove ```sql ... ``` wrapping from LLM output."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return text
````

### Utils — Pure Functions

Utils are pure functions with no side effects, no database access, no API calls.

Put logic here when it's a calculation, transformation, or formatting task
that could be reused across services, pipeline steps, CLI scripts, or tests.

Utils are the easiest code to test — no mocks needed, just input → output.

---

## Dependency Injection Wiring

All DI wiring lives in `backend/src/dry_data/api/dependencies.py`. This is the
**only place** where concrete implementations are instantiated.

```python
# dependencies.py — the ONLY place concrete classes are created
import duckdb
from fastapi import Depends
from openai import AsyncOpenAI

from dry_data.config import settings
from dry_data.warehouse.repository import DataRepository
from dry_data.llm.openai_provider import OpenAIProvider
from dry_data.services.query_service import QueryService


def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Open a read-only DuckDB connection."""
    return duckdb.connect(str(settings.db_path), read_only=True)


def get_data_repo(
    con: duckdb.DuckDBPyConnection = Depends(get_db_connection),
) -> DataRepository:
    return DataRepository(con=con)


def get_llm_provider() -> OpenAIProvider:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    return OpenAIProvider(client=client, model=settings.openai_model)


def get_query_service(
    data_repo: DataRepository = Depends(get_data_repo),
    llm_provider: OpenAIProvider = Depends(get_llm_provider),
) -> QueryService:
    return QueryService(data_repo=data_repo, llm_provider=llm_provider)
```

**When creating a new service or repository, always add its factory function here.**

If you need to swap OpenAI for another provider, change `get_llm_provider()` —
nothing else in the codebase needs to change.

---

## Domain Exceptions

This project uses domain exceptions, not HTTPException, in services and
repositories. Routes catch domain exceptions and convert them to HTTP responses.

| Exception        | Meaning                                        | Typical HTTP mapping |
| ---------------- | ---------------------------------------------- | -------------------- |
| `IngestionError` | Data download or raw file handling failed      | 502                  |
| `TransformError` | Data cleaning or transformation failed         | 500                  |
| `WarehouseError` | DuckDB schema or loading failed                | 500                  |
| `QueryError`     | User query is unsafe or execution failed       | 400                  |
| `LLMError`       | OpenAI call failed or returned unusable output | 502                  |

Never raise `HTTPException` outside of route files.

---

## Pydantic Models

**All Pydantic models live in `dry_data/models/`.** Don't scatter model
definitions across service or repository modules — centralize them.

```
dry_data/
├── models/
│   ├── __init__.py        # Re-export commonly used models
│   ├── api.py             # Request/response shapes (QueryRequest, QueryResponse)
│   ├── warehouse.py       # TableSchema, ColumnInfo, QueryResult
│   ├── datasets.py        # DatasetInfo, DatasetSummary
│   └── llm.py             # PlotlySpec, LLMPromptContext
```

**Rules:**

- Every model used by more than one module goes here.
- Import from `dry_data.models.api`, `dry_data.models.warehouse`, etc.
- Re-export the most common ones from `models/__init__.py` for convenience.
- Never define Pydantic models inside service, repository, or route files.

**Return Pydantic models from services and repositories, not raw dicts or tuples.**

```python
# BAD — caller has to guess what's in the dict
async def get_schema(self, table: str) -> dict:
    return {"columns": [...], "row_count": 42}

# GOOD — caller uses named fields, IDE autocomplete works
async def get_schema(self, table: str) -> TableSchema:
    return TableSchema(columns=[...], row_count=42)
```

---

## Polars Conventions

### Lazy by Default

```python
# GOOD
result = (
    pl.scan_parquet("data/cleaned/who/consumption.parquet")
    .filter(pl.col("year") >= 2010)
    .group_by("country_name")
    .agg(pl.col("liters_pure_alcohol_pc").mean())
    .collect()
)

# BAD — eager, no optimization
df = pl.read_parquet("data/cleaned/who/consumption.parquet")
df = df.filter(pl.col("year") >= 2010)
```

### Use Expressions, Not Loops

```python
# GOOD
df.with_columns(
    pl.when(pl.col("ALCDAY5") == 888).then(0)
    .when(pl.col("ALCDAY5") == 777).then(None)
    .otherwise(pl.col("ALCDAY5"))
    .alias("drink_days_30d")
)

# BAD
for i in range(len(df)):
    if df[i, "ALCDAY5"] == 888: ...
```

### Schema Declarations

Every transform module declares expected input and output schemas at the top.
Column names: source codes get renamed to descriptive snake_case during
the transform step. The warehouse never sees raw source codes.

---

## DuckDB Patterns

### Parameterized Queries Only

```python
# GOOD
con.execute("SELECT * FROM dim_state WHERE state_abbr = ?", [state])

# BAD
con.execute(f"SELECT * FROM dim_state WHERE state_abbr = '{state}'")
```

### Loading Parquet

DuckDB reads Parquet natively. Validate column alignment before loading.

---

## Ingestor Pattern

All ingestors extend `BaseIngestor` from `ingest/base.py`.

- Use `httpx` for HTTP, not `requests`.
- Wrap network calls with `tenacity` retry (3 attempts, exponential backoff).
- Validate downloads: file size > 0, expected format.
- Raise `IngestionError` on failure, never return silently.
- Idempotent: re-running overwrites, doesn't create duplicates.

---

## Transformer Pattern

All transformers extend `BaseTransformer` from `transform/base.py`.

- Use Polars lazy evaluation where possible.
- Declare input and output schemas at module top.
- Validate aggressively: raise `TransformError` on schema mismatches.
- One Parquet file per output table.
- Shared logic (country name normalization) in `transform/dimensions.py`.

---

## MCP Server Security

Tools: `list_datasets`, `get_schema`, `query_data`, `summarize_column`.

**Non-negotiable:**

- Reject SQL containing: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER,
  ATTACH, COPY, EXPORT, IMPORT.
- Enforce row limit (default 1000).
- Set query timeout (default 30 seconds).

---

## LLM Integration

- Prompts are modular. Schema context is injected dynamically per query.
- Parse defensively: strip markdown fences, handle empty responses.
- The LLM returns Plotly figure specs (`data` + `layout`). Frontend renders
  directly via `react-plotly.js`.
- Never expose raw API errors to users. Wrap in `LLMError`.
- Use `tenacity` retry on all OpenAI calls.

---

## New Feature Checklist

Create files in this order:

1. **Models** — Pydantic models in `models/` package (new file or add to existing)
2. **Repository** — Data access, domain exceptions
3. **Provider** — External API wrapper behind ABC (if needed)
4. **Service** — Business logic, orchestrates repos + providers
5. **Dependencies** — Factory functions in `api/dependencies.py`
6. **Routes** — Thin endpoints, DI via `Depends()`
7. **Tests** — Following the testing-discipline skill

### Per-file checks:

- [ ] Type hints on all function signatures
- [ ] Docstrings on all public functions and classes
- [ ] Domain exceptions (not HTTPException) in repos/services
- [ ] Dependencies injected via `__init__`, never instantiated locally
- [ ] Parameterized DuckDB queries (never string interpolation)
- [ ] Pydantic return types from repos and services
- [ ] `tenacity` retry on external API calls
- [ ] Provider pattern (ABC + concrete) for any new external service

---

## File Conventions

- **Imports**: Use `X | None` directly (Python 3.11+, no `Optional`).
- **Logging**: `structlog.get_logger()` at module level. No `print()`.
- **Paths**: Always `pathlib.Path`. Never string concatenation.
- **Config**: Import `settings` from `dry_data.config`. Never read env vars directly.
- **Constants**: `SCREAMING_SNAKE_CASE` at module top.

---

## After Every Change

```bash
cd backend
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run pytest tests/ -x -q
```

All three must pass before considering the work done.
