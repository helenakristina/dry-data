---
name: testing-discipline
description: >
  Use when implementing any feature, bugfix, or refactor in the Dry Data project.
  Enforces honest testing practices across the monorepo: FastAPI + DuckDB + Polars +
  OpenAI backend and React + TypeScript + Plotly frontend. Prioritizes tests that prove
  behavior over tests that confirm implementation. Activates for new features, bug fixes,
  refactoring, data pipeline work, and code review. Always use this skill alongside the
  backend-development or frontend-development skills.
version: 1.0.0
languages: [python, typescript]
---

# Testing Discipline — Dry Data

## The Core Problem This Skill Solves

When the same AI session writes code AND tests, the tests tend to be tautological —
they verify what was built, not what was required. This skill breaks that cycle.

**The question is never "does my code work?" It's "would this test catch the bug?"**

## Golden Rule

```
Every test must be able to fail for a meaningful reason.
If you can't describe a realistic bug this test would catch, the test is worthless.
```

Before writing any test, state in a comment:

```python
# CATCHES: [description of a realistic bug this test would detect]
```

```typescript
// CATCHES: [description of a realistic bug this test would detect]
```

If you can't fill in the blank, don't write the test.

---

## Decision: New Code vs. Existing Code

```
Is this NEW code or a CHANGE to existing code?

NEW CODE ──────► Write test first (TDD).
                 Watch it fail.
                 Implement minimally.
                 See "TDD for New Code" below.

EXISTING CODE ─► Write characterization test first.
                 Prove current behavior.
                 THEN write failing test for new behavior.
                 See "Changing Existing Code" below.
```

---

## TDD for New Code

For any new function, endpoint, pipeline step, or component: write the test before
the implementation.

### The Cycle

1. **RED** — Write one test describing desired behavior. Run it. Watch it fail.
2. **Verify RED** — Confirm it fails because the feature is missing, not because of
   a typo, import error, or missing fixture.
3. **GREEN** — Write the minimum code to make the test pass. Nothing more.
4. **Verify GREEN** — Run the test. Run the full suite. Everything green.
5. **REFACTOR** — Clean up. Keep tests green. Don't add behavior.
6. **Repeat** — Next behavior, next test.

### The Iron Law (New Code Only)

```
No implementation code without a failing test first.
```

Wrote implementation before the test? Don't retrofit tests onto it.
Delete the implementation. Write the test. Watch it fail. Reimplement.

---

## Changing Existing Code

### Steps

1. **Characterize** — Write a test that captures the current behavior, even if you
   think the behavior is wrong. Run it. It should pass.
2. **Specify** — Write a new test for the desired behavior change. It should fail.
3. **Implement** — Change the code to make the new test pass.
4. **Verify** — Both the characterization test (if behavior should be preserved) and
   the new test should pass. If the characterization test now fails, that's expected
   only if you're intentionally changing that behavior — be explicit about it.

---

## Backend Testing Rules

### Stack context: FastAPI + DuckDB + Polars + OpenAI + MCP server

### The Mock Problem

**Rules for mocking:**

```
MOCK ONLY WHAT YOU DON'T OWN.

External APIs (OpenAI, FRED, Google Trends) ────► Mock at the boundary
DuckDB ─────────────────────────────────────────► Use real in-memory DuckDB (it's fast)
Polars DataFrames ──────────────────────────────► Use real DataFrames with small test data
Your own functions and classes ─────────────────► Do not mock. Use the real thing.
File system (downloads) ────────────────────────► Use tmp_path fixture, real files
```

DuckDB in-memory is fast enough to use as a real test database. Never mock it.
Polars DataFrames are cheap to construct. Never mock them.

### What to Test at Each Layer

#### Ingestors (`ingest/*.py`)

Test that download logic handles real-world failure modes. Mock only the HTTP
calls — test everything else with real file I/O into `tmp_path`.

```python
# CATCHES: Ingestor silently returns empty list when the remote server returns
#          a 403 instead of raising IngestionError
def test_who_ingestor_raises_on_http_error(tmp_path, httpx_mock):
    httpx_mock.add_response(status_code=403)
    ingestor = WHOIngestor()
    ingestor._raw_dir = tmp_path  # override for test isolation
    with pytest.raises(IngestionError):
        ingestor.download()
```

```python
# CATCHES: Downloaded file is empty (0 bytes) but ingestor reports success
def test_who_ingestor_rejects_empty_download(tmp_path, httpx_mock):
    httpx_mock.add_response(content=b"")
    ingestor = WHOIngestor()
    ingestor._raw_dir = tmp_path
    with pytest.raises(IngestionError, match="empty"):
        ingestor.download()
```

#### Transformers (`transform/*.py`)

This is the most bug-prone layer. Test thoroughly with real Polars operations on
small DataFrames. Focus on:

- Column mapping (source codes → readable names)
- Null/missing value handling
- Type casting edge cases
- Row filtering (are the right rows kept/dropped?)
- Output schema validation

```python
# CATCHES: Transformer maps BRFSS code 88 ("none") to 88 drinks instead of 0
def test_brfss_transform_maps_none_code_to_zero():
    raw = pl.DataFrame({"ALCDAY5": [201, 888, 777]})
    result = transform_alcohol_frequency(raw)
    assert result["drink_days_30d"].to_list() == [1, 0, None]
```

```python
# CATCHES: Country name normalization misses "Türkiye" → "Turkey" mapping,
#          causing join failures with the dimension table
def test_who_transform_normalizes_country_names():
    raw = pl.DataFrame({"country": ["Türkiye", "United States of America", "Côte d'Ivoire"]})
    result = normalize_country_names(raw)
    assert "Turkey" in result["country_name"].to_list()
    assert "United States" in result["country_name"].to_list()
```

```python
# CATCHES: Transform silently drops rows with null values in non-nullable
#          columns instead of raising TransformError
def test_transform_rejects_nulls_in_required_columns():
    raw = pl.DataFrame({"year": [2022, None, 2024], "value": [1.0, 2.0, 3.0]})
    with pytest.raises(TransformError, match="null"):
        validate_required_columns(raw, required=["year"])
```

**Key principle for transform tests:** Construct the simplest possible input
DataFrame that exercises one behavior. Don't reuse large fixtures across
unrelated tests — each test should make its own small DataFrame.

#### Warehouse / DuckDB (`warehouse/*.py`)

Use real in-memory DuckDB. The `db` fixture in `conftest.py` provides one with
the full schema already created.

```python
# CATCHES: Loader silently skips Parquet columns that don't match the DuckDB
#          schema instead of raising WarehouseError
def test_loader_rejects_schema_mismatch(db, tmp_path):
    bad_df = pl.DataFrame({"wrong_column": [1, 2, 3]})
    bad_df.write_parquet(tmp_path / "bad.parquet")
    with pytest.raises(WarehouseError):
        load_parquet_to_table(db, tmp_path / "bad.parquet", "fact_brfss_responses")
```

```python
# CATCHES: Loader appends duplicate rows on re-run instead of replacing
def test_loader_is_idempotent(db, sample_parquet):
    load_parquet_to_table(db, sample_parquet, "fact_us_spending")
    load_parquet_to_table(db, sample_parquet, "fact_us_spending")
    count = db.execute("SELECT count(*) FROM fact_us_spending").fetchone()[0]
    assert count == 3  # same as one load, not doubled
```

#### MCP Server (`mcp_server/*.py`)

Test the tool implementations directly — they're just functions that take
parameters and return results. Use a real DuckDB connection.

```python
# CATCHES: query_data tool allows DROP TABLE through SQL injection
def test_query_tool_rejects_destructive_sql(db):
    with pytest.raises(QueryError, match="prohibited"):
        query_data(db, "DROP TABLE fact_brfss_responses")
```

```python
# CATCHES: query_data returns unlimited rows, causing memory explosion on
#          SELECT * from a table with 1M+ rows
def test_query_tool_enforces_row_limit(db, sample_dim_year):
    result = query_data(db, "SELECT * FROM dim_year", max_rows=2)
    assert len(result["rows"]) <= 2
```

```python
# CATCHES: get_schema returns column names but not types, making the LLM
#          unable to construct valid SQL
def test_get_schema_includes_column_types(db):
    schema = get_schema(db, "dim_state")
    assert all("type" in col for col in schema["columns"])
```

#### LLM Integration (`llm/*.py`)

Mock the OpenAI client. Test everything around it: prompt construction,
response parsing, error handling.

```python
# CATCHES: Prompt builder injects the full schema for ALL tables even when
#          the question only references one, blowing the token budget
def test_prompt_builder_selects_relevant_tables():
    prompt = build_schema_context("How much do Americans spend on alcohol?")
    assert "fact_us_spending" in prompt
    assert "fact_brfss_responses" not in prompt
```

````python
# CATCHES: Chain crashes when OpenAI returns SQL wrapped in markdown fences
#          instead of raw SQL
def test_chain_strips_markdown_fences_from_sql(mock_openai):
    mock_openai.chat.completions.create.return_value = mock_completion(
        "```sql\nSELECT * FROM dim_year\n```"
    )
    result = await generate_sql("What years do you have?")
    assert not result.startswith("```")
    assert result.strip() == "SELECT * FROM dim_year"
````

```python
# CATCHES: Chain returns the raw LLM error message to the user instead of
#          a friendly error when OpenAI returns a rate limit response
def test_chain_handles_rate_limit_gracefully(mock_openai):
    mock_openai.chat.completions.create.side_effect = openai.RateLimitError(
        "Rate limit exceeded", response=mock_response(429), body={}
    )
    result = await answer_question("test question")
    assert result.error is not None
    assert "rate limit" not in result.error.lower()  # no raw error leak
```

#### API Endpoints (`api/routes/*.py`)

Use `httpx.AsyncClient` with the real FastAPI app. Mock only the OpenAI client.

```python
# CATCHES: POST /api/query returns 200 with an empty string question instead
#          of 422 validation error
async def test_query_endpoint_rejects_empty_question(client):
    response = await client.post("/api/query", json={"question": ""})
    assert response.status_code == 422
```

```python
# CATCHES: GET /api/datasets crashes when DuckDB file doesn't exist yet
#          (first run before pipeline)
async def test_datasets_endpoint_handles_empty_db(client_no_data):
    response = await client_no_data.get("/api/datasets")
    assert response.status_code == 200
    assert response.json() == []
```

### Backend Anti-Patterns (Do NOT Do These)

| Anti-pattern                                     | Problem                              | Do this instead                            |
| ------------------------------------------------ | ------------------------------------ | ------------------------------------------ |
| Mocking DuckDB                                   | Tests prove nothing about queries    | Use real in-memory DuckDB                  |
| Mocking Polars DataFrames                        | Tests prove nothing about transforms | Use real small DataFrames                  |
| `assert mock.called_with(...)` as only assertion | Tests the call, not the result       | Assert on return values                    |
| One giant fixture DataFrame for all tests        | Tests are coupled, hard to read      | Each test builds its own small input       |
| Mocking your own service classes                 | Tautological                         | Call the real service, mock only externals |
| `@pytest.mark.parametrize` with 20 trivial cases | Coverage theater                     | Parametrize only for different code paths  |
| Testing that Polars `.filter()` filters          | Tests the library, not your code     | Test your filter _condition_ is correct    |

---

## Frontend Testing Rules

### Stack context: React + TypeScript + Plotly + Vite

### Setup

- **Vitest** as test runner
- **@testing-library/react** for component tests
- **jsdom** as the DOM environment
- **msw** (Mock Service Worker) for API mocking

### What to Test

#### Components

Test from the user's perspective. Render, interact, assert on what's visible.

```typescript
// CATCHES: Chat submit fires with an empty input, sending a blank question to the API
test("disables send button when input is empty", () => {
  render(<ChatInterface />);
  const sendButton = screen.getByRole("button", { name: /send/i });
  expect(sendButton).toBeDisabled();
});
```

```typescript
// CATCHES: Starter question cards disappear after first message but the chat
//          area shows nothing — user sees a blank screen
test("shows message history after submitting a question", async () => {
  render(<ChatInterface />);
  const starterButton = screen.getByText(/Which countries drink the most/i);
  await userEvent.click(starterButton);

  expect(screen.getByText(/Which countries drink the most/i)).toBeInTheDocument();
  expect(screen.queryByText(/What do you want to explore/i)).not.toBeInTheDocument();
});
```

```typescript
// CATCHES: SQL details section is always visible instead of hidden behind
//          a disclosure toggle
test("hides SQL by default, shows on click", async () => {
  render(<ChatMessage message={messageWithSQL} />);
  expect(screen.queryByText(/SELECT/)).not.toBeInTheDocument();

  await userEvent.click(screen.getByText(/View SQL/i));
  expect(screen.getByText(/SELECT/)).toBeInTheDocument();
});
```

#### ChartRenderer

Don't test Plotly internals. Test that your component passes the right props
and handles edge cases.

```typescript
// CATCHES: ChartRenderer crashes when chart spec has empty data array
//          instead of showing a graceful empty state
test("renders empty state when data array is empty", () => {
  const spec = { data: [], layout: { title: "Empty" } };
  render(<ChartRenderer spec={spec} />);
  // Should not throw — verify it renders without error
  expect(screen.getByText(/no data/i)).toBeInTheDocument();
});
```

```typescript
// CATCHES: ChartRenderer ignores the layout title from the LLM response,
//          showing the base layout title instead
test("uses layout title from spec", () => {
  const spec = {
    data: [{ type: "bar" as const, x: ["A"], y: [1] }],
    layout: { title: "Alcohol Spending Over Time" },
  };
  const { container } = render(<ChartRenderer spec={spec} />);
  // Plotly renders title in the DOM
  expect(container.textContent).toContain("Alcohol Spending Over Time");
});
```

#### API Client

Mock fetch or use MSW. Test your wrapper's behavior, not fetch itself.

```typescript
// CATCHES: API client doesn't throw on 500 responses, silently returning
//          undefined and causing downstream crashes
test("throws ApiError on server error", async () => {
  server.use(
    http.post("/api/query", () => {
      return HttpResponse.json({ detail: "Internal error" }, { status: 500 });
    }),
  );

  await expect(queryData("test question")).rejects.toThrow(ApiError);
});
```

#### DatasetBrowser

```typescript
// CATCHES: Dataset browser crashes when backend returns empty array
//          (pipeline hasn't run yet)
test("shows empty state when no datasets loaded", async () => {
  server.use(
    http.get("/api/datasets", () => {
      return HttpResponse.json([]);
    }),
  );

  render(<DatasetBrowser />);
  await waitFor(() => {
    expect(screen.getByText(/no datasets/i)).toBeInTheDocument();
  });
});
```

### Frontend Anti-Patterns

| Anti-pattern                       | Problem                             | Do this instead                                |
| ---------------------------------- | ----------------------------------- | ---------------------------------------------- |
| Testing component state directly   | Brittle, breaks on refactor         | Test what the user sees                        |
| Snapshot tests on components       | Always break, nobody reads diffs    | Test specific behaviors                        |
| `getByTestId` everywhere           | Tests don't reflect user experience | Use `getByRole`, `getByLabelText`, `getByText` |
| Mocking Plotly to test charts      | Tests nothing real                  | Test your props/config logic, not the library  |
| Testing that `useState` sets state | Tests React, not your code          | Test visible outcomes of state changes         |

---

## The Self-Confirmation Problem

This is the #1 risk when AI writes both code and tests in the same session.

### How to Catch It

After writing tests for new code, apply this check:

```
For each test, ask:
  1. Could this test pass with a WRONG implementation?
  2. If I introduced [specific realistic bug], would this test catch it?
  3. Does this test assert on BEHAVIOR or on IMPLEMENTATION DETAILS?
```

If #1 is yes → test needs to be stronger.
If #2 is no → test is missing something.
If #3 is "implementation details" → rewrite it.

### The Mutation Check

After writing tests, mentally introduce a bug:

- Off-by-one in a Polars filter
- Wrong column name in a DuckDB query
- Swapped conditional in SQL validation
- Missing null check in a transformer
- Wrong status code in an API route

Would the tests catch it? If not, they're confirming implementation, not
guarding behavior.

**Claude: when you write tests, include a "mutation note" in your response
listing 2-3 specific bugs these tests would catch. If you can't list any,
the tests aren't good enough.**

---

## Data Pipeline Testing — Special Rules

Data pipelines have unique failure modes. Apply these rules in addition to the
layer-specific rules above.

### Test the seams, not the plumbing

```
DON'T test: "Does Polars read a Parquet file?"  (tests the library)
DO test:    "Does MY transform produce the right columns from THIS raw input?"
```

### Test with realistic edge cases

Real-world data is messy. Your test DataFrames should include:

- Null values in columns you expect to be non-null
- Unicode characters in country/state names
- Extreme values (0, negative, very large)
- Duplicate rows
- Mismatched types (string where int expected)

```python
# CATCHES: Transform crashes on Unicode country names like "Réunion" or
#          "São Tomé and Príncipe"
def test_transform_handles_unicode_country_names():
    raw = pl.DataFrame({"country": ["Réunion", "São Tomé and Príncipe"]})
    result = normalize_country_names(raw)
    assert result.height == 2  # both rows preserved
```

### Test schema contracts between layers

The transform output must match what the warehouse expects. Test this explicitly.

```python
# CATCHES: Transform adds a new column that doesn't exist in the DuckDB
#          schema, causing the loader to silently drop it
def test_who_transform_output_matches_warehouse_schema(db):
    expected_cols = {
        row[0] for row in
        db.execute("DESCRIBE fact_global_consumption").fetchall()
    }
    result = WHOTransformer().transform()
    parquet_cols = set(pl.read_parquet_schema(result[0]).keys())
    assert parquet_cols.issubset(expected_cols)
```

### Test idempotency

Every pipeline step must be safe to re-run.

```python
# CATCHES: Running the ingestor twice creates duplicate files in raw/
def test_ingestor_overwrites_on_rerun(tmp_path, httpx_mock):
    httpx_mock.add_response(content=b"data")
    ingestor = FREDIngestor()
    ingestor._raw_dir = tmp_path
    ingestor.download()
    ingestor.download()  # second run
    assert len(list(tmp_path.iterdir())) == 1  # not 2
```

---

## Quick Reference

```
NEW CODE         → TDD (test first, watch fail, implement, watch pass)
EXISTING CODE    → Characterize current behavior, then test-first for changes
BACKEND MOCKS    → Mock only external APIs (OpenAI, FRED, Google Trends)
DUCKDB           → Always use real in-memory DuckDB, never mock
POLARS           → Always use real DataFrames, never mock
TRANSFORMS       → Test column mappings, nulls, types, edge cases thoroughly
MCP SERVER       → Test SQL injection protection, row limits, schema exposure
FRONTEND TESTS   → Test on touch. User perspective. No snapshots.
PLOTLY           → Test your config/props, not the library
DATA PIPELINES   → Test schema contracts between layers, test idempotency
EVERY TEST       → Must have a "CATCHES:" comment
AI-WRITTEN CODE  → Include mutation notes. Challenge test quality in review.
```
