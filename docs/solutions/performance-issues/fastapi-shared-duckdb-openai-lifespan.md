---
title: FastAPI Lifespan for Shared DuckDB Connection and AsyncOpenAI Client
category: performance-issues
date: 2026-03-21
tags: [fastapi, duckdb, openai, lifespan, dependency-injection, performance]
---

# FastAPI Lifespan for Shared DuckDB Connection and AsyncOpenAI Client

## Problem

Creating a DuckDB connection per request pays a file-lock acquisition cost (~10–50ms).
Creating an `AsyncOpenAI` client per request opens a new `httpx.AsyncClient` and pays
a TLS handshake on cold connections (~200–500ms to `api.openai.com`).

Both resources are thread/coroutine-safe and designed to be shared.

## Solution

Use FastAPI's `lifespan` async context manager to create shared resources once at
startup and close them cleanly at shutdown.

### app.py

```python
from contextlib import asynccontextmanager
import duckdb
from openai import AsyncOpenAI
from fastapi import FastAPI
from dry_data.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared resources once; close them on shutdown."""
    try:
        app.state.db = duckdb.connect(str(settings.db_path), read_only=True)
    except Exception:
        logger.warning("lifespan.db.missing — API will fail on DB-dependent routes")
        app.state.db = None
    app.state.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    yield
    if app.state.db:
        app.state.db.close()
    await app.state.openai_client.close()

app = FastAPI(lifespan=lifespan, ...)
```

The `try/except` around DuckDB connection allows the app to start in test environments
where the DB file doesn't exist — tests override the `get_db_connection` dependency
entirely, so `app.state.db` is never accessed.

### dependencies.py

```python
from fastapi import Request

def get_db_connection(request: Request) -> duckdb.DuckDBPyConnection:
    return request.app.state.db

def get_llm_provider(request: Request) -> LLMProviderBase:
    return OpenAIProvider(
        client=request.app.state.openai_client,
        model=settings.openai_model,
    )
```

### Test compatibility

Tests using `app.dependency_overrides[get_db_connection] = lambda: test_db` continue
to work unchanged — the override completely replaces the function, so `app.state.db`
is never accessed by test code.

```python
# test_routes.py — no changes needed
app.dependency_overrides[get_db_connection] = lambda: db_fixture
app.dependency_overrides[get_llm_provider] = lambda: mock_provider
```

## Bonus: asyncio.gather for independent LLM calls

When two LLM API calls are independent (neither depends on the other's output),
run them concurrently with `return_exceptions=True` for resilience:

```python
import asyncio
from dry_data.exceptions import LLMError

narrate_result, chart_result = await asyncio.gather(
    self._llm.narrate_results(question, results),
    self._llm.suggest_chart(question, results),
    return_exceptions=True,
)

if isinstance(narrate_result, Exception):
    raise LLMError(str(narrate_result)) from narrate_result

narrative = narrate_result
chart = None if isinstance(chart_result, Exception) else chart_result
```

`return_exceptions=True` means chart failure doesn't kill the narration — the user
still gets a text answer even if chart generation fails.

## Prevention

- Any new expensive resource (Redis client, S3 client, etc.) should be initialized in
  `lifespan`, not in a dependency function
- Keep `get_db_connection` and `get_llm_provider` as thin functions that read from
  `app.state` — this preserves test override compatibility

## Related Files

- `backend/src/dry_data/api/app.py` — `lifespan` context manager
- `backend/src/dry_data/api/dependencies.py` — `get_db_connection`, `get_llm_provider`
- `backend/src/dry_data/services/query_service.py` — `asyncio.gather` usage
