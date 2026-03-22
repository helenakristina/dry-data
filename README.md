# Dry Data 🔍📊

A data journalism platform that lets you explore alcohol-related trends through
interactive visualizations and natural language queries.

Ask questions like:
- "Which US states have the highest binge drinking rates?"
- "How has alcohol consumption changed in Scandinavian countries since 2000?"
- "Show me the Google Trends data for 'sober curious' vs 'dry january'"

...and get narrative answers with auto-generated charts.

## What this is

Dry Data is a **data exploration and journalism tool** — not a health app.
It presents publicly available population-level statistics from sources like
the CDC, WHO, Bureau of Labor Statistics, and Google Trends.

It does **not** collect user health data, provide medical advice, track
anyone's drinking, or make personalized health recommendations.

## Tech stack

- **Data**: Polars + DuckDB (star schema)
- **LLM**: OpenAI GPT-4o for natural language → SQL translation
- **Integration**: Custom MCP server exposing data tools
- **API**: FastAPI
- **Frontend**: React + TypeScript + Recharts

## Data sources

| Source | What | Size |
|--------|------|------|
| CDC BRFSS | US behavioral risk factor surveys | ~450k rows/year |
| WHO / Our World in Data | Global alcohol consumption by country | 190+ countries |
| FRED / BLS | US household alcohol spending | 1984–present |
| Google Trends | Search interest for sober-curious terms | Weekly since 2004 |

All data is publicly available and freely licensed.

## Quick start

```bash
# Clone and set up
git clone <repo-url> && cd dry-data

# Configure
cp .env.example .env
# Edit .env with your API keys

# Backend
cd backend
uv sync
uv run pytest tests/ -x -q              # verify everything passes
cd ..

# Frontend (no create-react-app needed — Vite scaffolding is already here)
cd frontend
npm install                       # install deps from package.json
npm run dev                       # starts dev server at http://localhost:3000
cd ..

# Run the data pipeline (after backend setup)
cd backend
uv run -m scripts.run_pipeline

# Start the API server
uv run uvicorn dry_data.api.app:app --port 8001 --reload
```

### How the frontend dev server works

You don't need `create-react-app` or any generator — the project is already
scaffolded with Vite. When you run `npm run dev`, Vite serves `index.html`
and hot-reloads any changes to `.tsx` files instantly. The `vite.config.ts`
proxies any `/api/*` requests to `localhost:8001`, so the frontend talks to
your FastAPI backend seamlessly during development.

For a production build: `npm run build` outputs static files to `frontend/dist/`
which FastAPI can serve, or you can deploy to any static host.

### Common gotchas

- **Frontend shows "Could not load datasets"**: The backend API isn't running.
  Start it with `uvicorn` first.
- **Charts don't render**: Make sure `npm install` completed — Plotly is ~1MB
  and can take a moment.
- **TypeScript errors after backend changes**: Update `frontend/src/types/api.ts`
  to match any new/changed Pydantic models.

## Project structure

See [CLAUDE.md](CLAUDE.md) for the full directory layout, coding conventions,
and architecture decisions.

## License

MIT
