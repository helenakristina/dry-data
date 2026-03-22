---
status: complete
priority: p2
issue_id: "009"
tags: [code-review, performance, architecture]
dependencies: []
---

# Per-Request DuckDB Connection and `AsyncOpenAI` Client — Should Be Shared/Pooled

## Problem Statement

Two expensive resources are recreated on every HTTP request:

1. **DuckDB connection** — `get_db_connection()` in `dependencies.py` opens a new
   file connection per request. DuckDB file lock acquisition has measurable overhead
   (~10–50ms) and can cause contention under concurrent load.

2. **`AsyncOpenAI` client** — `get_llm_provider()` creates a new `AsyncOpenAI()`
   instance per request. Each instance initialises a new `httpx.AsyncClient` with a
   new connection pool, meaning every query opens a fresh TCP connection to
   `api.openai.com` and pays the TLS handshake cost (~200–500ms on a cold connection).

Both resources are safe to share across requests and should be created once at startup.

## Findings

- `backend/src/dry_data/api/dependencies.py`:
  - `get_db_connection()` — creates new `duckdb.connect()` per request
  - `get_llm_provider()` — creates new `AsyncOpenAI()` per request
- FastAPI supports application lifespan events (`@asynccontextmanager` on `lifespan`)
  for startup/shutdown resource management
- `AsyncOpenAI` is documented as safe for concurrent use — one instance per process

## Proposed Solutions

### Option 1: FastAPI lifespan context for shared resources (recommended)

**Approach:** Use FastAPI's `lifespan` parameter to create shared resources once:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.db = duckdb.connect(settings.duckdb_path, read_only=True)
    app.state.openai = AsyncOpenAI(api_key=settings.openai_api_key)
    yield
    # Shutdown
    app.state.db.close()
    await app.state.openai.close()

app = FastAPI(lifespan=lifespan)
```

Then update `get_db_connection` and `get_llm_provider` to pull from `app.state`.

**Pros:**
- Eliminates per-request overhead for both resources
- Clean startup/shutdown lifecycle
- FastAPI's official recommended pattern

**Cons:**
- Requires updating dependency functions to accept `Request` or use app-level state
- Test overrides need updating

**Effort:** 2–3 hours

**Risk:** Low-medium (touches dependency injection plumbing)

---

### Option 2: Module-level singletons

**Approach:** Create singletons at module import time in `dependencies.py`.

**Pros:** Simpler

**Cons:**
- Harder to test (module-level state is sticky)
- No clean shutdown hook

**Effort:** 1 hour

**Risk:** Medium (testing friction)

## Recommended Action

Option 1. The lifespan pattern is FastAPI-idiomatic and makes the resource lifecycle
explicit.

## Technical Details

**Affected files:**
- `backend/src/dry_data/api/app.py` — add `lifespan` parameter
- `backend/src/dry_data/api/dependencies.py` — update `get_db_connection`, `get_llm_provider`
- `backend/tests/test_api/test_routes.py` — update dependency overrides

## Acceptance Criteria

- [ ] DuckDB connection is opened once at startup, closed at shutdown
- [ ] `AsyncOpenAI` client is created once at startup
- [ ] API tests still pass with dependency overrides
- [ ] Concurrent requests share the same DB connection without errors

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (performance-oracle + architecture-strategist agents)
