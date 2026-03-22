---
status: complete
priority: p2
issue_id: "010"
tags: [code-review, architecture]
dependencies: []
---

# `repository_base.py` Imports `DatasetInfo` from `api/models` — Layer Violation

## Problem Statement

`BaseDataRepository` in the warehouse layer imports `DatasetInfo` from
`dry_data.api.models`. The warehouse layer should not depend on the API layer —
it's the wrong direction in the dependency graph. This makes the warehouse layer
impossible to use without loading FastAPI/Pydantic API models, and tightly couples
two layers that should be independent.

The correct direction is: API layer → service layer → warehouse layer (one-way).

## Findings

- `backend/src/dry_data/warehouse/repository_base.py`:
  ```python
  from dry_data.api.models import DatasetInfo  # wrong layer direction
  ```
- `DatasetInfo` is a simple dataclass/Pydantic model describing a table name and
  description — it belongs in a shared domain types module, not the API layer
- This also means importing `repository_base` in tests pulls in all of FastAPI

## Proposed Solutions

### Option 1: Move `DatasetInfo` to a shared `dry_data/types.py` or `dry_data/models.py`

**Approach:**
1. Create `backend/src/dry_data/domain.py` (or `types.py`) with `DatasetInfo`
2. Import from there in both `repository_base.py` and `api/models.py`

```python
# dry_data/domain.py
from pydantic import BaseModel

class DatasetInfo(BaseModel):
    table_name: str
    description: str
    row_count: int | None = None
```

**Pros:**
- Fixes the layer violation
- `DatasetInfo` is accessible to both warehouse and API layers
- Clean import graph

**Cons:**
- Small migration: update imports in all files that use `DatasetInfo`

**Effort:** 30–45 minutes

**Risk:** Low

---

### Option 2: Inline a plain dataclass in `repository_base.py`

**Approach:** Define `DatasetInfo` as a `dataclass` directly in `repository_base.py`
and re-export it from `api/models.py`.

**Pros:** No new file

**Cons:** `DatasetInfo` ends up in the warehouse module, which is also odd

**Effort:** 15 minutes

**Risk:** Low

## Recommended Action

Option 1 — creating a `domain.py` or `types.py` for shared domain models is the
standard pattern and will be needed for future data types anyway.

## Technical Details

**Affected files:**
- `backend/src/dry_data/warehouse/repository_base.py` — update import
- `backend/src/dry_data/api/models.py` — re-export or update import
- `backend/src/dry_data/api/routes/datasets.py` — likely uses `DatasetInfo`
- New file: `backend/src/dry_data/domain.py`

## Acceptance Criteria

- [ ] `repository_base.py` does not import from `dry_data.api.*`
- [ ] `DatasetInfo` lives in a shared module importable by both layers
- [ ] All tests pass
- [ ] `ruff check` passes

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (architecture-strategist agent)
