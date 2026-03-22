---
status: complete
priority: p1
issue_id: "002"
tags: [code-review, security]
dependencies: []
---

# SQL Blocklist Missing Dangerous Keywords (TRUNCATE, PRAGMA, SET, CALL, LOAD, INSTALL)

## Problem Statement

`BaseDataRepository._validate_sql` rejects a handful of write keywords but misses several
others that can cause serious harm in DuckDB:

- `TRUNCATE` — wipes an entire table
- `PRAGMA` — toggles security and memory settings
- `SET` — changes DuckDB session configuration
- `CALL` — invokes stored procedures
- `LOAD` / `INSTALL` — loads native extensions, potential arbitrary code execution

Because the LLM generates SQL that passes through `execute_safe_query`, a prompt-injected
or misgenerated query containing any of these keywords would execute unimpeded.

## Findings

- `backend/src/dry_data/warehouse/repository_base.py` — `_FORBIDDEN_PATTERN`:
  ```python
  _FORBIDDEN_PATTERN = re.compile(
      r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|EXPORT|IMPORT)\b",
      re.IGNORECASE
  )
  ```
- Missing: `TRUNCATE`, `PRAGMA`, `SET`, `CALL`, `LOAD`, `INSTALL`, `VACUUM`
- DuckDB `LOAD 'httpfs'` can make outbound network requests from the DB process
- DuckDB `INSTALL` downloads and installs extensions

## Proposed Solutions

### Option 1: Expand the regex blocklist (recommended)

**Approach:** Add all missing dangerous keywords to `_FORBIDDEN_PATTERN`:
```python
_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|EXPORT|IMPORT"
    r"|TRUNCATE|PRAGMA|SET|CALL|LOAD|INSTALL|VACUUM)\b",
    re.IGNORECASE,
)
```

**Pros:**
- Minimal change, consistent with existing approach
- Immediately closes the gaps

**Cons:**
- `SET` is broad — may reject valid column aliases like `SET_ID` (word boundary `\b`
  mitigates this, but worth testing)

**Effort:** 15 minutes

**Risk:** Low

---

### Option 2: Allowlist-only approach

**Approach:** Instead of blocking known-bad, only allow `SELECT` statements:
```python
if not sql.strip().upper().startswith("SELECT"):
    raise WarehouseError("Only SELECT queries are permitted")
```

**Pros:**
- Structurally safe — unknown future keywords can't slip through
- Simpler mental model

**Cons:**
- CTEs (`WITH ... SELECT`) and some valid `COPY TO` exports start with non-SELECT
- May be too restrictive if future use cases require read-only DuckDB features

**Effort:** 30 minutes (plus updating tests)

**Risk:** Low-medium (may require test updates)

## Recommended Action

Option 1 for now (quickest fix, lowest risk). File a follow-up to evaluate moving to
Option 2 (allowlist) once the MCP server is implemented.

## Technical Details

**Affected files:**
- `backend/src/dry_data/warehouse/repository_base.py` — `_FORBIDDEN_PATTERN` constant
- `backend/tests/test_warehouse/test_repository_base.py` — add tests for new keywords

## Acceptance Criteria

- [ ] `TRUNCATE`, `PRAGMA`, `SET`, `CALL`, `LOAD`, `INSTALL` all raise `WarehouseError`
- [ ] New tests added for each newly blocked keyword
- [ ] Existing tests still pass
- [ ] `ruff check` passes

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (security-sentinel agent)

**Actions:**
- Audited `_FORBIDDEN_PATTERN` against DuckDB's dangerous statement list
- Identified 6 missing keywords
