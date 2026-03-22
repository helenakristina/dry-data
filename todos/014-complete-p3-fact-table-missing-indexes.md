---
status: complete
priority: p3
issue_id: "014"
tags: [code-review, performance, architecture]
dependencies: []
---

# No Indexes on Fact Table FK Columns — Queries Will Scan Full Table

## Problem Statement

The DuckDB star schema has fact tables (e.g. `fact_global_consumption`) with foreign
key columns (`country_id`, `year_id`, `sex`) but no indexes on them. Every query that
filters or joins on these columns triggers a full table scan. At the current data scale
(~6,000 rows) this is unnoticeable, but as additional data sources are added
(BRFSS, FRED, Google Trends) the fact tables will grow significantly.

DuckDB supports `CREATE INDEX` and uses ART (Adaptive Radix Tree) indexes for
point-lookup and range queries.

## Findings

- `backend/src/dry_data/warehouse/schema.py` — DDL for `fact_global_consumption`:
  No `CREATE INDEX` statements after table creation
- `year_id`, `country_id`, `sex` are the primary filter/join columns in all analytical queries
- DuckDB automatically creates indexes for PRIMARY KEY constraints, but FK columns
  used in WHERE clauses still benefit from explicit indexes

## Proposed Solutions

### Option 1: Add `CREATE INDEX IF NOT EXISTS` statements to schema.py

**Approach:**
```sql
CREATE INDEX IF NOT EXISTS idx_fact_global_consumption_year
    ON fact_global_consumption (year_id);

CREATE INDEX IF NOT EXISTS idx_fact_global_consumption_country
    ON fact_global_consumption (country_id);

CREATE INDEX IF NOT EXISTS idx_fact_global_consumption_sex
    ON fact_global_consumption (sex);
```

Add these after each fact table DDL in `schema.py`.

**Pros:**
- Applied once at schema creation, maintained automatically
- Improves join and filter performance
- Standard practice for analytical star schemas

**Cons:**
- Small write overhead on INSERT/UPDATE (negligible for batch loads)
- DuckDB may choose not to use them for small tables (query planner decides)

**Effort:** 30 minutes

**Risk:** Low

---

### Option 2: Defer until performance benchmarks show a problem

**Approach:** Leave as-is and add indexes when query latency becomes measurable.

**Pros:** No premature optimization

**Cons:**
- Harder to add indexes later (requires schema migration + data reload)
- Better to establish the pattern now

**Effort:** 0

**Risk:** Low (current scale)

## Recommended Action

Option 1 — indexes are cheap and establishing the pattern now avoids a harder
migration later.

## Technical Details

**Affected files:**
- `backend/src/dry_data/warehouse/schema.py` — add `CREATE INDEX` statements
- Drop and recreate the DB to apply (or use `CREATE INDEX IF NOT EXISTS`)

## Acceptance Criteria

- [ ] FK columns on all fact tables have `CREATE INDEX IF NOT EXISTS`
- [ ] Schema creation script is idempotent
- [ ] `EXPLAIN` on a filtered fact query shows index usage

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (architecture-strategist agent)
