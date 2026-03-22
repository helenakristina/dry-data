---
status: pending
priority: p2
issue_id: "005"
tags: [code-review, performance]
dependencies: []
---

# `narrate_results` and `suggest_chart` Run Sequentially — Should Use `asyncio.gather`

## Problem Statement

In `QueryService.answer_question()`, the narration and chart suggestion LLM calls are
made sequentially:

```python
narrative = await provider.narrate_results(question, sql, rows)
chart = await provider.suggest_chart(question, rows)
```

Both calls are independent (neither depends on the other's output). Each is a separate
OpenAI API call with ~1–3 second latency. Running them sequentially adds unnecessary
latency to every user query.

## Findings

- `backend/src/dry_data/services/query_service.py` — `answer_question` method
- Both `narrate_results` and `suggest_chart` are `async` methods with no data dependency
- Using `asyncio.gather` would halve the LLM portion of the response time (from ~4–6s
  to ~2–3s)
- OpenAI API supports concurrent requests from the same key

## Proposed Solutions

### Option 1: `asyncio.gather` (recommended)

**Approach:**
```python
import asyncio

narrative, chart = await asyncio.gather(
    provider.narrate_results(question, sql, rows),
    provider.suggest_chart(question, rows),
)
```

**Pros:**
- Cuts LLM latency roughly in half for every query
- Zero complexity overhead — `asyncio.gather` is stdlib
- Errors propagate naturally (first exception wins unless `return_exceptions=True`)

**Cons:**
- Error handling: if `suggest_chart` fails, `narrate_results` is also cancelled. May
  want `return_exceptions=True` and handle individually.

**Effort:** 30 minutes (including test update)

**Risk:** Low

---

### Option 2: `asyncio.gather` with `return_exceptions=True`

**Approach:**
```python
results = await asyncio.gather(
    provider.narrate_results(question, sql, rows),
    provider.suggest_chart(question, rows),
    return_exceptions=True,
)
narrative = results[0] if not isinstance(results[0], Exception) else ""
chart = results[1] if not isinstance(results[1], Exception) else None
```

**Pros:**
- More resilient — chart failure doesn't kill narration
- Better user experience (still get text answer even if chart fails)

**Cons:**
- Slightly more verbose
- Need to re-raise `LLMError` if narration itself fails

**Effort:** 45 minutes

**Risk:** Low

## Recommended Action

Option 2 — the extra resilience is worth the few extra lines given that chart generation
is optional and shouldn't block a text answer.

## Technical Details

**Affected files:**
- `backend/src/dry_data/services/query_service.py` — `answer_question` method
- `backend/tests/test_services/test_query_service.py` — update mocks if needed

## Acceptance Criteria

- [ ] `narrate_results` and `suggest_chart` are called concurrently via `asyncio.gather`
- [ ] Chart failure does not suppress the narration result
- [ ] Existing service tests pass
- [ ] `ruff check` passes

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (performance-oracle agent)
