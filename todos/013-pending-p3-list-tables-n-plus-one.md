---
status: pending
priority: p3
issue_id: "013"
tags: [code-review, performance]
dependencies: []
---

# `list_tables` Issues N+1 DuckDB Queries (~16 per `/api/datasets` call)

## Problem Statement

`BaseDataRepository.list_tables()` calls `get_table_descriptions()` which iterates
over tables and issues a separate DuckDB query for each one (e.g. `COUNT(*)` or
schema introspection). With ~16 tables in the warehouse, every call to
`GET /api/datasets` executes 16+ sequential queries.

While each query is fast (in-process DuckDB), the pattern doesn't scale and adds
unnecessary latency on every datasets list load.

## Findings

- `backend/src/dry_data/warehouse/repository_base.py` — `list_tables` and/or
  `get_table_descriptions` methods
- Pattern: `for table_name in tables: conn.execute(f"SELECT COUNT(*) FROM {table_name}")`
  (or similar per-table queries)
- 16 round-trips × ~1ms each = ~16ms unnecessary overhead per request
- DuckDB supports aggregating across tables in a single query via `information_schema`

## Proposed Solutions

### Option 1: Batch count query using `information_schema` or `UNION ALL`

**Approach:** Build a single `UNION ALL` query to count all tables at once:

```python
tables = conn.execute(
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
).fetchall()

union_sql = " UNION ALL ".join(
    f"SELECT '{t}' AS table_name, COUNT(*) AS row_count FROM {t}"
    for t in table_names
)
counts = dict(conn.execute(union_sql).fetchall())
```

Or use DuckDB's `duckdb_tables()` function which returns row counts directly.

**Pros:**
- 1 query instead of N
- Simple implementation

**Cons:**
- Dynamic SQL construction (use with trusted table names only — warehouse-controlled)

**Effort:** 1 hour

**Risk:** Low

---

### Option 2: Cache the table list with a short TTL

**Approach:** Cache the result of `list_tables()` for 60 seconds using `functools.lru_cache`
or `cachetools.TTLCache`.

**Pros:**
- Zero query changes; handles future N+1 patterns too
- Very low effort

**Cons:**
- Stale data after pipeline reload (acceptable for 60s)
- `lru_cache` doesn't work well with instance methods

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Option 1 — the batch query is the correct fix. Cache can be added on top if needed.

## Technical Details

**Affected files:**
- `backend/src/dry_data/warehouse/repository_base.py` — `list_tables` / `get_table_descriptions`
- `backend/tests/test_warehouse/test_repository_base.py` — verify test still passes

## Acceptance Criteria

- [ ] `list_tables()` issues at most 2 DuckDB queries regardless of table count
- [ ] Existing tests pass
- [ ] `ruff check` passes

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (performance-oracle agent)
