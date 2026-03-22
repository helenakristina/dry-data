---
status: pending
priority: p2
issue_id: "006"
tags: [code-review, architecture, data-integrity]
dependencies: []
---

# `DELETE + INSERT` in Fact Loader Not Wrapped in a Transaction

## Problem Statement

The WHO fact loader deletes existing rows then inserts new ones in two separate
operations. If the process is interrupted between them (crash, OOM, SIGTERM), the
table is left empty — corrupting the warehouse. Since DuckDB is the only data store
(no read replica, no rollback), data loss here means re-running the full pipeline.

## Findings

- Loader file (likely `backend/src/dry_data/warehouse/loader.py` or similar):
  ```python
  conn.execute("DELETE FROM fact_global_consumption")
  conn.execute("COPY fact_global_consumption FROM '...' (FORMAT PARQUET)")
  ```
  (or equivalent INSERT FROM SELECT pattern)
- No explicit `BEGIN` / `COMMIT` wrapping these two statements
- DuckDB auto-commits each statement by default
- If the COPY/INSERT fails after DELETE, the fact table is permanently empty until
  the pipeline is rerun

## Proposed Solutions

### Option 1: Wrap in explicit transaction (recommended)

**Approach:**
```python
conn.execute("BEGIN")
try:
    conn.execute("DELETE FROM fact_global_consumption")
    conn.execute("COPY fact_global_consumption FROM ? (FORMAT PARQUET)", [str(path)])
    conn.execute("COMMIT")
except Exception:
    conn.execute("ROLLBACK")
    raise
```

Or use DuckDB's context manager if available:
```python
with conn.transaction():
    conn.execute("DELETE FROM fact_global_consumption")
    conn.execute(...)
```

**Pros:**
- Atomic: either both succeed or neither takes effect
- Standard database best practice

**Cons:** None meaningful

**Effort:** 30 minutes

**Risk:** Low

---

### Option 2: Write to a staging table, then swap (blue/green)

**Approach:**
```python
conn.execute("CREATE TABLE fact_global_consumption_new AS SELECT * FROM ...")
conn.execute("DROP TABLE fact_global_consumption")
conn.execute("ALTER TABLE fact_global_consumption_new RENAME TO fact_global_consumption")
```

**Pros:**
- Zero downtime: the original table is readable until the swap
- Good if the API reads from the DB concurrently during pipeline runs

**Cons:**
- Requires recreating indexes after rename
- More complex

**Effort:** 1–2 hours

**Risk:** Medium

## Recommended Action

Option 1 for now. Option 2 is a future improvement if concurrent reads during pipeline
runs become a concern.

## Technical Details

**Affected files:**
- `backend/src/dry_data/warehouse/loader.py` (or wherever the DELETE+INSERT lives)

## Acceptance Criteria

- [ ] `DELETE` and subsequent `INSERT`/`COPY` for each fact table are in a single transaction
- [ ] On simulated failure mid-load, the original rows are preserved
- [ ] `ruff check` passes

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (architecture-strategist + performance-oracle agents)
