---
status: complete
priority: p1
issue_id: "001"
tags: [code-review, security]
dependencies: []
---

# SQL Injection via Unparameterized `table_name` f-string in `get_table_schema`

## Problem Statement

`BaseDataRepository.get_table_schema()` interpolates the caller-supplied `table_name`
argument directly into a SQL string using an f-string. Any code path that passes an
attacker-controlled or LLM-generated string here can execute arbitrary SQL — completely
bypassing the blocklist that `execute_safe_query` relies on.

This is especially dangerous because the QueryService calls this with schema names derived
from the LLM's output during NL→SQL generation.

## Findings

- `backend/src/dry_data/warehouse/repository_base.py` — `get_table_schema` method:
  ```python
  sql = f"SELECT column_name, data_type ... WHERE table_name = '{table_name}'"
  ```
  The `table_name` is concatenated, not parameterized.
- DuckDB supports `?` positional parameters via `execute(sql, [params])`. Parameterized
  queries are already the stated convention in CLAUDE.md ("Parameterized queries only").
- The `execute_safe_query` blocklist is irrelevant here: the injection point is in the
  WHERE clause, so a payload like `' OR '1'='1` doesn't need any forbidden keyword.

## Proposed Solutions

### Option 1: Parameterize the query (recommended)

**Approach:** Replace the f-string with a `?` placeholder:
```python
sql = """
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = ?
ORDER BY ordinal_position
"""
conn.execute(sql, [table_name])
```

**Pros:**
- Correct fix — eliminates the injection vector entirely
- Consistent with CLAUDE.md "parameterized queries only" rule
- One-line change

**Cons:** None

**Effort:** 15 minutes

**Risk:** Low

---

### Option 2: Allowlist validation before interpolation

**Approach:** Query `information_schema.tables` first, confirm `table_name` is a real
table, then interpolate.

**Pros:** Catches typos too

**Cons:** Still two round-trips; parameterization is simpler and more correct

**Effort:** 30 minutes

**Risk:** Low (but Option 1 is strictly better)

## Recommended Action

Implement Option 1 immediately. This is a one-line fix.

## Technical Details

**Affected files:**
- `backend/src/dry_data/warehouse/repository_base.py` — `get_table_schema` method

## Resources

- CLAUDE.md: "Parameterized queries only. Never interpolate user input into SQL strings."
- DuckDB parameterized query docs: use `conn.execute(sql, params)` with `?` placeholders

## Acceptance Criteria

- [ ] `get_table_schema` uses `?` placeholder — no f-string interpolation of `table_name`
- [ ] Existing test `test_schema_includes_types` still passes
- [ ] `ruff check` passes

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (security-sentinel + architecture-strategist agents)

**Actions:**
- Flagged during multi-agent review of the full WHO/OWID implementation
- Confirmed f-string interpolation in `repository_base.py`

**Learnings:**
- The blocklist in `execute_safe_query` is not a substitute for parameterized queries
