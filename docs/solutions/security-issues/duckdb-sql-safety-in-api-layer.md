---
title: DuckDB SQL Safety in a Read-Only API Layer
category: security-issues
date: 2026-03-21
tags: [duckdb, sql-injection, security, api, repository-pattern]
---

# DuckDB SQL Safety in a Read-Only API Layer

## Problem

When an API layer executes SQL that originates from user input or an LLM, two injection
vectors exist:

1. **Keyword injection** — user/LLM includes `DROP`, `TRUNCATE`, `LOAD 'httpfs'`, etc.
   in a SELECT query via prompt injection or SQL smuggling.
2. **Identifier injection** — dynamic table names are interpolated via f-string into
   a query where a `?` placeholder is not valid (SQL identifiers cannot be parameterized).

DuckDB-specific dangerous keywords missing from naive blocklists:

| Keyword | Risk |
|---------|------|
| `TRUNCATE` | Wipes a table without a WHERE clause |
| `PRAGMA` | Toggles internal DuckDB settings |
| `SET` | Changes session-level configuration |
| `CALL` | Invokes stored procedures |
| `LOAD` | Loads a native extension (e.g. `LOAD 'httpfs'` enables outbound HTTP) |
| `INSTALL` | Downloads and installs extensions |
| `VACUUM` | Can block reads while running |

## Solution

### 1. Comprehensive keyword blocklist

```python
# backend/src/dry_data/warehouse/repository_base.py
_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|EXPORT|IMPORT"
    r"|TRUNCATE|PRAGMA|SET|CALL|LOAD|INSTALL|VACUUM)\b",
    re.IGNORECASE,
)
```

### 2. Quoted-identifier escaping for dynamic table names

DuckDB does not support `?` placeholders for identifiers (only for values). When a
table name must be interpolated:

```python
# Safe: escape embedded double-quotes and wrap in double-quotes
safe_name = '"' + table_name.replace('"', '""') + '"'
row_count = con.execute(f"SELECT COUNT(*) FROM {safe_name}").fetchone()[0]
```

This follows the SQL standard for identifier quoting (same as PostgreSQL `quote_ident`).

### 3. Row limit enforcement

Always cap result sets from LLM-generated queries:

```python
def execute_safe_query(self, sql: str, max_rows: int = 1000) -> QueryResult:
    self._validate_sql(sql)
    relation = self._con.execute(sql)
    rows = [list(row) for row in relation.fetchmany(max_rows)]
    return QueryResult(columns=[d[0] for d in relation.description], rows=rows)
```

### 4. Future: allowlist over blocklist

A more robust long-term approach is to assert the query starts with `SELECT` or `WITH`
rather than blocking known-bad keywords:

```python
stripped = sql.strip().upper()
if not (stripped.startswith("SELECT") or stripped.startswith("WITH")):
    raise QueryError("Only SELECT queries are permitted")
```

Combine with the keyword blocklist for defence-in-depth until this is fully adopted.

## Prevention

- Never pass user input or LLM output directly to `con.execute()` without going through
  `execute_safe_query`
- When adding a new repository method that constructs SQL with dynamic identifiers
  (table/column names), always use the double-quote escaping pattern
- All blocklist keywords should have a corresponding test

## Related Files

- `backend/src/dry_data/warehouse/repository_base.py` — `_FORBIDDEN_PATTERN`, `execute_safe_query`, `get_table_schema`
- `backend/tests/test_warehouse/test_repository_base.py` — keyword rejection tests
