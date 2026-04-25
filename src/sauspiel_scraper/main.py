import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from sauspiel_scraper.app import process_game_data
from sauspiel_scraper.core import SauspielScraper
from sauspiel_scraper.repository import Database

app = typer.Typer(help="Sauspiel Game Scraper CLI")
console = Console()


@app.command()
def export(

    username: Annotated[str, typer.Option("--username", "-u", envvar="USERNAME", prompt=True)],
    db_path: Annotated[Path, typer.Option("--db")] = Path("output/sauspiel.db"),
    output_path: Annotated[Path, typer.Option("--output", "-o")] = Path("output/export.jsonl"),
) -> None:
    """Export games from database to JSONL format."""
    db = Database(db_path)
    games = db.get_all_games()
    if not games:
        console.print("[yellow]No games found in database.[/]")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for game in games:
            f.write(game.model_dump_json(exclude_unset=True) + "\n")
    
    console.print(f"[green]Exported {len(games)} game records to {output_path}[/]")


@app.command()
def scrape(
    username: Annotated[str, typer.Option("--username", "-u", envvar="USERNAME", prompt=True)],
    password: Annotated[
        str, typer.Option("--password", "-p", envvar="PASSWORD", prompt=True, hide_input=True)
    ],
    count: Annotated[int | None, typer.Option("--count", "-c")] = 20,
    since: Annotated[str | None, typer.Option("--since", "-s")] = None,
    db_path: Annotated[Path, typer.Option("--db")] = Path("output/sauspiel.db"),
) -> None:
    """Scrape games and save them to a SQLite database."""
    since_dt = datetime.strptime(since, "%d.%m.%Y") if since else None
    db = Database(db_path)
    scraper = SauspielScraper(username, password)

    with console.status(f"Logging in as {username}..."):
        if not scraper.login():
            console.print("[red]Login failed.[/]")
            raise typer.Exit(1)

    with console.status("Fetching game list..."):
        new_games = scraper.get_game_list_paginated(max_new=count or 20, since=since_dt, db=db)

    if not new_games:
        console.print("[yellow]No new games to scrape.[/]")
        return

    console.print(f"Scraping {len(new_games)} new games...")
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping...", total=len(new_games))
        for info in new_games:
            gid = info.game_id
            progress.update(task, description=f"Scraping {gid}")
            try:
                # Core method now handles retries and waiting
                data = scraper.scrape_game(gid, info, log_func=console.print)
                if data:
                    db.save_game(data)
            except Exception as e:
                console.print(f"\n[bold red]Fatal error for {gid}: {e}[/]")
                break
            
            progress.advance(task)

    console.print(f"[green]Done! Database updated: {db_path}[/]")


if __name__ == "__main__":
    app()
