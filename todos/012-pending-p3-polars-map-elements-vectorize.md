---
status: pending
priority: p3
issue_id: "012"
tags: [code-review, performance]
dependencies: []
---

# `map_elements(normalize_country_name)` Should Use Vectorised Polars Expression

## Problem Statement

`WHOTransformer._build_total_rows()` and `_build_sex_rows()` both call:
```python
pl.col("Entity").map_elements(normalize_country_name, return_dtype=pl.Utf8)
```

`map_elements` drops to Python-level row iteration — it's the Polars equivalent of
a `for` loop, losing all the performance benefits of Polars' Rust-based execution
engine. For the ~200-country, ~21-year dataset this is fine today, but it's an
anti-pattern per CLAUDE.md ("Use expressions, not loops").

## Findings

- `backend/src/dry_data/transform/who.py`:
  - `_build_total_rows` line ~200: `map_elements(normalize_country_name, ...)`
  - `_build_sex_rows` line ~241: same pattern
- `normalize_country_name` in `transform/dimensions.py` — likely does string
  cleaning (strip whitespace, fix unicode, etc.)
- If `normalize_country_name` only does simple string ops, it can be replaced with
  Polars expressions entirely (`.str.strip_chars()`, `.str.replace()`, etc.)

## Proposed Solutions

### Option 1: Replace with Polars string expressions (if logic is simple enough)

**Approach:** Inspect `normalize_country_name` and replace with equivalent
Polars expressions:
```python
pl.col("Entity").str.strip_chars().str.replace_all(r"\s+", " ")
```

**Pros:**
- Fully vectorised, executes in Rust
- No Python overhead per row

**Cons:**
- May not cover all edge cases `normalize_country_name` handles (unicode, etc.)
- Requires careful review of `normalize_country_name`'s logic

**Effort:** 1–2 hours

**Risk:** Low-medium (must verify correctness against existing tests)

---

### Option 2: Keep `map_elements` but document it as intentional

**Approach:** Add a comment explaining why Python-level iteration is acceptable:
```python
# map_elements necessary: normalize_country_name handles complex unicode
# edge cases not expressible as Polars string expressions.
```

**Pros:** Zero risk, honest about the trade-off

**Cons:** Doesn't fix the performance issue (acceptable at current data scale)

**Effort:** 5 minutes

**Risk:** None

## Recommended Action

Option 1 if the logic is simple. Option 2 if `normalize_country_name` handles complex
logic that can't be expressed in Polars. Investigate first.

## Technical Details

**Affected files:**
- `backend/src/dry_data/transform/who.py`
- `backend/src/dry_data/transform/dimensions.py` — `normalize_country_name` definition

## Acceptance Criteria

- [ ] `map_elements` is either replaced with a vectorised expression OR documented
      as intentionally non-vectorised
- [ ] All transform tests pass with identical output
- [ ] `ruff check` passes

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (performance-oracle agent)
