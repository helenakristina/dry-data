---
status: complete
priority: p2
issue_id: "011"
tags: [code-review, typescript, ux]
dependencies: []
---

# `StoryChart` Shows "Loading…" Forever on API Failure — No Error State

## Problem Statement

`StoryChart.tsx` silently swallows errors from `getGlobalTrend()` and leaves `spec`
as `null`, which renders the "Loading chart…" spinner indefinitely. A user visiting
the landing page when the backend is down (or the story endpoint returns an error)
will see a permanent loading state with no indication that something went wrong.

The comment in the code says "Silent: story chart failure should not break the landing
page" — the intent is correct (don't hard-crash), but silently spinning is poor UX.

## Findings

- `frontend/src/components/StoryChart.tsx`:
  ```tsx
  .catch(() => {
    // Silent: story chart failure should not break the landing page.
  });
  ```
  `spec` stays `null` → renders `<p>Loading chart…</p>` forever
- The component has no `error` state
- A failed state like "Chart unavailable" is far friendlier than an eternal spinner

## Proposed Solutions

### Option 1: Add `failed` boolean state (recommended)

**Approach:**
```tsx
const [spec, setSpec] = useState<PlotlySpec | null>(null);
const [failed, setFailed] = useState(false);

// in useEffect:
.catch(() => {
  if (!cancelled) setFailed(true);
});

// in render:
if (failed) {
  return (
    <p className="py-4 text-center text-sm text-gray-400">
      Chart unavailable — try refreshing.
    </p>
  );
}
if (!spec) {
  return <p className="py-4 text-center text-sm text-gray-400">Loading chart…</p>;
}
```

**Pros:**
- Clear user feedback
- No library needed
- Keeps silent-fail intent (no hard crash, just graceful degradation)

**Cons:** None

**Effort:** 20 minutes

**Risk:** Low

---

### Option 2: Use a loading/error/data state enum

**Approach:** `useState<'loading' | 'error' | 'loaded'>('loading')`

**Pros:** More explicit state machine
**Cons:** Minor over-engineering for a single-fetch component

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Option 1 — simple, clear, matches the existing pattern in the component.

## Technical Details

**Affected files:**
- `frontend/src/components/StoryChart.tsx`
- `frontend/src/components/__tests__/StoryChart.test.tsx` (add test for failed state)

## Acceptance Criteria

- [ ] When `getGlobalTrend()` rejects, `StoryChart` renders a "Chart unavailable" message
- [ ] "Loading chart…" is not shown after a failed fetch
- [ ] Vitest test covers the error state with an MSW error handler
- [ ] `npm run typecheck` passes

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (kieran-typescript-reviewer agent)
