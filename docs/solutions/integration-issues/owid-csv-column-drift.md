---
title: OWID CSV Column Name Drift — Candidate List Pattern
category: integration-issues
date: 2026-03-21
tags: [owid, who, csv, transform, polars, data-sources]
---

# OWID CSV Column Name Drift — Candidate List Pattern

## Problem

Our World in Data (OWID) renames CSV column headers between dataset versions with no
deprecation notice. The WHO alcohol consumption dataset changed columns like:

| Old name | New name |
|----------|----------|
| `Alcohol consumption per capita – WHO version (liters of pure alcohol)` | `Alcohol consumption` |
| `Alcohol consumption per capita, male – WHO version (liters of pure alcohol)` | `Men` |
| `Alcohol consumption per capita, female – WHO version (liters of pure alcohol)` | `Women` |
| `Indicator:Alcohol, drinkers only consumption (APC) - Data by country` | `Alcohol, consumers past 12 months (%) - Sex: both sexes` |

The URL slug also changed:
- Old: `share-of-adults-who-drink-alcohol.csv`
- New: `share-of-adults-who-drank-alcohol-in-last-year.csv`

**Symptom:** `TransformError: Expected one of [...] but found columns: [...]` on pipeline run
after OWID updates their dataset.

## Root Cause

OWID uses `useColumnShortNames=false` in the CSV export URL, but they still rename both
the "long" names and the URL slugs when they update or reframe a dataset.

## Solution

Define **ordered candidate lists** for each value column in the transformer module:

```python
# backend/src/dry_data/transform/who.py

CONSUMPTION_VALUE_CANDIDATES = [
    "Alcohol consumption",                                                           # current OWID name
    "Alcohol consumption per capita – WHO version (liters of pure alcohol)",         # legacy
    "total_alcohol",                                                                 # short name
]
MALE_VALUE_CANDIDATES = [
    "Men",                                                                           # current
    "Alcohol consumption per capita, male – WHO version (liters of pure alcohol)",   # legacy
    "male_alcohol",
]
# ... etc.

def _detect_value_col(df: pl.DataFrame, candidates: list[str]) -> str:
    """Return the first candidate column name that exists in df."""
    for col in candidates:
        if col in df.columns:
            return col
    raise TransformError(f"Expected one of {candidates} but found columns: {df.columns}")
```

**Rule:** Always prepend the **current** OWID name to the list. Keep old names as
fallbacks. This makes old local cached CSVs still work after an OWID update, and
new downloads work after a rename.

## Prevention

When adding a new OWID data source:
1. Inspect the actual CSV headers before writing the transformer
2. Define candidate lists immediately — even if there's only one name now
3. Use `useColumnShortNames=false` in the download URL to get stable long names
4. Watch the OWID changelog if a dataset starts producing `TransformError` in CI

## Related Files

- `backend/src/dry_data/transform/who.py` — `*_VALUE_CANDIDATES` lists
- `backend/src/dry_data/ingest/who.py` — `SOURCES` list with URLs
