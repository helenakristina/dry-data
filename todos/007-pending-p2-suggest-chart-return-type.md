---
status: pending
priority: p2
issue_id: "007"
tags: [code-review, architecture, typescript]
dependencies: []
---

# `suggest_chart` Returns `dict | None` — Should Return `PlotlySpec | None`

## Problem Statement

`OpenAIProvider.suggest_chart()` is typed to return `dict | None`, but `PlotlySpec` is
the domain type used everywhere else for Plotly figures. Using `dict` breaks the type
chain: the QueryService assigns chart output to `QueryResponse.chart` which expects
`PlotlySpec | None`, and the frontend `ChartRenderer` receives `PlotlySpec`. The
current typing forces implicit downcasting and defeats the TypeScript/Pydantic contract.

Additionally, the `LLMProviderBase` ABC declares `suggest_chart` with `dict | None`,
which means any future provider is also incorrectly typed.

## Findings

- `backend/src/dry_data/llm/base.py` — abstract method signature: `-> dict | None`
- `backend/src/dry_data/llm/openai_provider.py` — concrete method: `-> dict | None`
- `backend/src/dry_data/api/models.py` — `QueryResponse.chart: PlotlySpec | None`
- `PlotlySpec` is defined in models and is the correct type

## Proposed Solutions

### Option 1: Change return type to `PlotlySpec | None` everywhere (recommended)

**Approach:**
1. Update `LLMProviderBase.suggest_chart` signature: `-> PlotlySpec | None`
2. Update `OpenAIProvider.suggest_chart` signature: `-> PlotlySpec | None`
3. In the implementation, wrap the parsed dict in `PlotlySpec(**parsed)` or validate via
   Pydantic before returning

```python
def suggest_chart(self, ...) -> PlotlySpec | None:
    ...
    try:
        parsed = json.loads(raw)
        return PlotlySpec(**parsed)  # validated by Pydantic
    except (json.JSONDecodeError, ValidationError):
        return None
```

**Pros:**
- End-to-end type safety from LLM → service → API → frontend contract
- Pydantic validation of the LLM chart spec (catches malformed specs before they reach
  `react-plotly.js`)
- Eliminates the implicit cast in QueryService

**Cons:**
- Requires `PlotlySpec` import in `llm/` layer — a mild layer concern (LLM layer knowing
  about API models), but `PlotlySpec` is a domain model, not an API concern

**Effort:** 45 minutes

**Risk:** Low

---

### Option 2: Introduce a `ChartSpec` domain type in a shared `types.py`

**Approach:** Move `PlotlySpec` (or create a `ChartSpec` alias) into
`dry_data/types.py` to avoid any layer coupling.

**Pros:** Cleaner architecture
**Cons:** Bigger refactor, low priority for now

**Effort:** 2 hours

**Risk:** Low-medium (touches many imports)

## Recommended Action

Option 1. The practical benefit (Pydantic validation of LLM output) outweighs the mild
layer concern.

## Technical Details

**Affected files:**
- `backend/src/dry_data/llm/base.py`
- `backend/src/dry_data/llm/openai_provider.py`
- `backend/src/dry_data/services/query_service.py` (remove any intermediate cast)
- `backend/tests/test_llm/test_openai_provider.py` (update assertions)

## Acceptance Criteria

- [ ] `suggest_chart` returns `PlotlySpec | None` in both base and implementation
- [ ] Returned value is Pydantic-validated (invalid LLM output returns `None`)
- [ ] `mypy` / `pyright` reports no type errors on `QueryResponse.chart = chart`
- [ ] Existing LLM and service tests pass

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (architecture-strategist + kieran-python-reviewer agents)
