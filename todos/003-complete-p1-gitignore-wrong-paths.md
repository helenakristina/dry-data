---
status: complete
priority: p1
issue_id: "003"
tags: [code-review, security]
dependencies: []
---

# `.gitignore` Has Wrong Frontend Paths — `node_modules` May Be Untracked

## Problem Statement

The `.gitignore` file references `src/frontend/` instead of the actual `frontend/`
directory. This means `frontend/node_modules/` is not ignored, and a `git add .` could
accidentally commit thousands of dependency files (or expose `node_modules` contents
in git history, which can include pre-built binaries and cached credentials).

Similarly, any other `frontend/`-scoped ignore rules are silently inactive.

## Findings

- `.gitignore` contains paths like `src/frontend/node_modules/` or similar with
  wrong prefix
- Actual frontend directory is `frontend/` (monorepo root sibling to `backend/`)
- CLAUDE.md explicitly lists `node_modules/` as "Never commit"
- `git status` may currently show `frontend/node_modules/` as untracked (depending
  on whether it was ever committed)

## Proposed Solutions

### Option 1: Fix the path prefix in `.gitignore`

**Approach:** Update all `src/frontend/` entries to `frontend/`:
```
# Before
src/frontend/node_modules/
src/frontend/dist/

# After
frontend/node_modules/
frontend/dist/
frontend/.vite/
```

Also verify `backend/` gitignore entries point to the correct location.

**Pros:**
- Direct fix
- Prevents accidental commits

**Cons:** None

**Effort:** 10 minutes

**Risk:** Low

---

### Option 2: Use root-level wildcards

**Approach:** Use `**/node_modules/` and `**/dist/` to catch any location:

**Pros:** More resilient to future directory restructuring

**Cons:** May be too broad if intentional `dist/` subdirectories exist

**Effort:** 10 minutes

**Risk:** Low

## Recommended Action

Option 2 — wildcards are more robust. Verify `git status` shows no `node_modules` as
untracked after the fix.

## Technical Details

**Affected files:**
- `.gitignore` at project root

**Verification steps:**
```bash
git status | grep node_modules  # should show nothing after fix
git ls-files frontend/node_modules/ | head  # should be empty
```

## Acceptance Criteria

- [ ] `frontend/node_modules/` is not shown in `git status`
- [ ] `frontend/dist/` is not shown in `git status`
- [ ] `git ls-files frontend/node_modules/` returns empty
- [ ] `.env` is also confirmed ignored

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (security-sentinel agent)

**Actions:**
- Noticed `.gitignore` path mismatch during review of project structure
