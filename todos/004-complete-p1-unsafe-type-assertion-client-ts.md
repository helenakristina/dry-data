---
status: complete
priority: p1
issue_id: "004"
tags: [code-review, security, typescript]
dependencies: []
---

# Unsafe Type Assertion in `client.ts` — `res.json() as Promise<T>`

## Problem Statement

`frontend/src/api/client.ts` casts the JSON response directly with `as Promise<T>` (or
`as T` after awaiting). TypeScript's `as` assertion silences the compiler but provides
zero runtime guarantee. If the API returns a different shape than expected — due to a
backend error, schema drift, or a future API change — the frontend will silently receive
a wrongly-typed object and fail in confusing, hard-to-debug ways downstream.

This is especially risky because the LLM generates the Plotly chart spec, which is then
passed straight to `react-plotly.js`. A malformed spec could crash the chart renderer.

## Findings

- `frontend/src/api/client.ts` — fetch wrapper pattern:
  ```typescript
  const res = await fetch(url, options);
  return res.json() as Promise<T>;  // or: return (await res.json()) as T;
  ```
  TypeScript accepts this but `res.json()` returns `Promise<any>` — the cast is vacuous.
- The correct pattern is `as unknown as T` to force the developer to acknowledge the
  type is unverified.
- A proper fix uses a runtime validator (Zod, Valibot, or a manual type guard).

## Proposed Solutions

### Option 1: `as unknown as T` intermediate cast (minimal)

**Approach:**
```typescript
return (await res.json()) as unknown as T;
```

**Pros:**
- Makes the unsafety explicit — forces acknowledgment
- TypeScript will flag naive `as T` patterns in future (stricter tsconfig)
- Zero runtime cost, zero new dependencies

**Cons:**
- Still no runtime guarantee; just honest about it

**Effort:** 15 minutes

**Risk:** Low

---

### Option 2: Zod schema validation at the API boundary (recommended long-term)

**Approach:** Define Zod schemas matching backend Pydantic models. Validate in the fetch
wrapper:
```typescript
async function apiFetch<T>(url: string, schema: z.ZodType<T>): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new ApiError(res.status);
  return schema.parse(await res.json());
}
```

**Pros:**
- Runtime type safety — API shape mismatches surface as clear errors
- Especially valuable for the Plotly spec from the LLM
- Good long-term investment

**Cons:**
- Requires `npm install zod` and defining schemas
- Medium effort

**Effort:** 2–3 hours

**Risk:** Low

## Recommended Action

Option 1 now (unblocks merge), Option 2 in a follow-up. The intermediate cast is
semantically honest and doesn't make things worse.

## Technical Details

**Affected files:**
- `frontend/src/api/client.ts` — all fetch wrapper return sites

## Acceptance Criteria

- [ ] No bare `as T` or `as Promise<T>` casts on `res.json()` output
- [ ] `npm run typecheck` passes
- [ ] Existing Vitest tests pass

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (kieran-typescript-reviewer agent)
