---
status: pending
priority: p2
issue_id: "008"
tags: [code-review, architecture, agent-native]
dependencies: []
---

# MCP Server Not Implemented — Agent-Native Parity Gap

## Problem Statement

The `mcp_server/` package exists in the directory structure (referenced in CLAUDE.md
and the project plan) but contains only an empty `__init__.py`. The four MCP tools
described in CLAUDE.md — `list_datasets`, `get_schema`, `query_data`,
`summarize_column` — are entirely absent.

This means no LLM agent can query the database directly. The current NL→SQL flow
goes through the FastAPI HTTP layer, which adds latency and is not the intended
architecture. More importantly, the MCP server is the canonical agent interface
described in the project spec — without it, agents cannot use Dry Data as intended.

## Findings

- `backend/src/dry_data/mcp_server/server.py` — missing or empty
- `backend/src/dry_data/mcp_server/tools.py` — missing or empty
- `backend/src/dry_data/warehouse/repository_base.py` has `list_tables`,
  `get_table_schema`, and `execute_safe_query` — all the building blocks are present
- `backend/src/dry_data/warehouse/queries.py` — `summarize_column` has no backend impl
- CLAUDE.md specifies the exact tool signatures to implement

## Proposed Solutions

### Option 1: Implement MCP server using `mcp` Python SDK (recommended)

**Approach:** Implement `server.py` and `tools.py` using the `mcp` SDK (already in
`pyproject.toml` dependencies if the project plan is complete):

```python
# tools.py
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("dry-data")

@server.tool()
async def list_datasets() -> list[dict]: ...

@server.tool()
async def get_schema(table_name: str) -> list[dict]: ...

@server.tool()
async def query_data(sql: str, limit: int = 1000) -> dict: ...

@server.tool()
async def summarize_column(table_name: str, column_name: str) -> dict: ...
```

**Pros:**
- Implements the architecture as designed
- Agents (Claude, GPT-4o) can call these tools directly
- `list_datasets` and `get_schema` can reuse `BaseDataRepository` methods
- `query_data` uses `execute_safe_query` — security already handled

**Cons:**
- Medium effort — need to wire DuckDB connection management for the MCP context
- Requires testing MCP tool call/response format

**Effort:** 4–6 hours

**Risk:** Medium (new integration surface)

---

### Option 2: Stub implementations with TODO markers

**Approach:** Add `raise NotImplementedError` stubs with clear docstrings.

**Pros:** Makes the gap explicit; unblocks other work

**Cons:** Doesn't solve the agent-native parity gap

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Option 1 — this is the core differentiating feature of the project. Schedule as a
dedicated work session after P1 items are resolved.

## Technical Details

**Affected files:**
- `backend/src/dry_data/mcp_server/server.py` (create)
- `backend/src/dry_data/mcp_server/tools.py` (create)
- `backend/src/dry_data/warehouse/queries.py` — implement `summarize_column`
- `backend/tests/test_mcp/` (create test module)

**From CLAUDE.md — required tools:**

| Tool | Description |
|------|-------------|
| `list_datasets` | Returns available fact/dim tables with descriptions |
| `get_schema` | Returns column names, types, sample values for a table |
| `query_data` | Executes a read-only SQL query, returns results as JSON |
| `summarize_column` | Returns stats (min, max, mean, nulls, top values) for a column |

## Acceptance Criteria

- [ ] `mcp_server/server.py` and `tools.py` are non-empty and importable
- [ ] All 4 tools (`list_datasets`, `get_schema`, `query_data`, `summarize_column`) implemented
- [ ] `query_data` enforces the SQL blocklist via `execute_safe_query`
- [ ] Tests cover each tool with in-memory DuckDB
- [ ] MCP server can be started with `uv run mcp run ...` or equivalent

## Work Log

### 2026-03-21 - Identified during code review

**By:** Claude Code (agent-native-reviewer agent)

**Learnings:**
- All repository building blocks (`list_tables`, `get_table_schema`, `execute_safe_query`)
  are already implemented — MCP tools are thin wrappers over these
