---
status: pending
priority: p3
issue_id: "015"
tags: [code-review, typescript, accessibility]
dependencies: []
---

# `DatasetBrowser` Missing `aria-expanded` + Vacuous Test

## Problem Statement

Two related issues in `DatasetBrowser`:

1. **Accessibility**: The expand/collapse toggle button is missing `aria-expanded`,
   which screen readers need to announce whether a section is open or closed. This
   fails WCAG 2.1 SC 4.1.2 (Name, Role, Value).

2. **Test quality**: The existing `DatasetBrowser` Vitest test only asserts
   `document.body` exists — a vacuous check that passes regardless of whether the
   component renders correctly.

## Findings

- `frontend/src/components/DatasetBrowser.tsx` — expand/collapse button:
  ```tsx
  <button onClick={() => setExpanded(!expanded)}>
    {dataset.name}
  </button>
  ```
  Missing: `aria-expanded={expanded}`

- `frontend/src/components/__tests__/DatasetBrowser.test.tsx` (or similar):
  ```typescript
  expect(document.body).toBeDefined();  // asserts nothing meaningful
  ```

## Proposed Solutions

### Option 1: Add `aria-expanded` + replace vacuous test (recommended)

**Fix 1 — aria-expanded:**
```tsx
<button
  onClick={() => setExpanded(!expanded)}
  aria-expanded={expanded}
  aria-controls={`dataset-${dataset.name}-details`}
>
  {dataset.name}
</button>
<div id={`dataset-${dataset.name}-details`}>
  {expanded && <DatasetDetails dataset={dataset} />}
</div>
```

**Fix 2 — meaningful test:**
```typescript
it("collapses and expands dataset details", async () => {
  render(<DatasetBrowser />);
  const button = screen.getByRole("button", { name: /fact_global_consumption/i });
  expect(button).toHaveAttribute("aria-expanded", "false");
  await userEvent.click(button);
  expect(button).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText(/liters_pure_alcohol_pc/i)).toBeInTheDocument();
});
```

**Pros:**
- Fixes both issues in one pass
- The new test actually proves expand/collapse behavior

**Cons:** None

**Effort:** 45 minutes

**Risk:** Low

## Recommended Action

Fix both together — they're in the same component and the same test file.

## Technical Details

**Affected files:**
- `frontend/src/components/DatasetBrowser.tsx`
- `frontend/src/components/__tests__/DatasetBrowser.test.tsx`

## Acceptance Criteria

- [ ] Expand/collapse button has `aria-expanded` reflecting current state
- [ ] Vitest test asserts meaningful component behavior (not `document.body`)
- [ ] `npm run typecheck` passes
- [ ] `npx vitest run` passes

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (kieran-typescript-reviewer + agent-native-reviewer agents)
