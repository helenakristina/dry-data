"""WHO data pipeline: download → transform → load.

Usage:
    uv run python -m scripts.run_pipeline
"""

import duckdb
import typer
from rich.console import Console
from rich.table import Table

from dry_data.config import settings
from dry_data.ingest.who import WHOIngestor
from dry_data.transform.who import WHOTransformer
from dry_data.warehouse.loader_who import load_all_who
from dry_data.warehouse.schema import create_all_tables

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Run the full WHO/OWID data pipeline end-to-end."""
    console.print("[bold blue]Dry Data — WHO Pipeline[/bold blue]")

    # 1. Ingest
    console.print("\n[yellow]Step 1/3:[/yellow] Downloading WHO/OWID CSVs...")
    ingestor = WHOIngestor()
    paths = ingestor.run()
    for p in paths:
        console.print(f"  ✓ {p.name} ({p.stat().st_size:,} bytes)")

    # 2. Transform
    console.print("\n[yellow]Step 2/3:[/yellow] Transforming to Parquet...")
    transformer = WHOTransformer()
    parquet_paths = transformer.run()
    for p in parquet_paths:
        console.print(f"  ✓ {p.name}")

    # 3. Load
    console.print("\n[yellow]Step 3/3:[/yellow] Loading into DuckDB...")
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.db_path))
    try:
        create_all_tables(con)
        cleaned_dir = settings.cleaned_dir / "who"
        load_all_who(con, cleaned_dir)
    finally:
        con.close()

    # 4. Summary
    console.print("\n[bold green]Pipeline complete![/bold green]\n")
    con_ro = duckdb.connect(str(settings.db_path), read_only=True)
    try:
        table = Table(title="Warehouse Summary", show_header=True)
        table.add_column("Table")
        table.add_column("Rows", justify="right")
        for tbl in [
            "dim_country",
            "dim_year",
            "dim_beverage_type",
            "fact_global_consumption",
        ]:
            count = con_ro.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0]
            table.add_row(tbl, f"{count:,}")
        console.print(table)
    finally:
        con_ro.close()


if __name__ == "__main__":
    app()
