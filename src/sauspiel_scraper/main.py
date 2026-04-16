import json
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from sauspiel_scraper.core import Database, SauspielScraper

app = typer.Typer(help="Sauspiel Game Scraper CLI")
console = Console()

@app.command()
def scrape(
    username: Annotated[str, typer.Option("--username", "-u", envvar="USERNAME", prompt=True)],
    password: Annotated[str, typer.Option("--password", "-p", envvar="PASSWORD", prompt=True, hide_input=True)],
    count: Annotated[Optional[int], typer.Option("--count", "-c")] = 20,
    since: Annotated[Optional[str], typer.Option("--since", "-s")] = None,
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
        game_list = scraper.get_game_list(limit=count, since=since_dt)
        new_games = [g for g in game_list if not db.game_exists(g["game_id"])]

    if not new_games:
        console.print("[yellow]No new games to scrape.[/]")
        return

    console.print(f"Scraping {len(new_games)} new games...")
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("Scraping...", total=len(new_games))
        for info in new_games:
            gid = info["game_id"]
            progress.update(task, description=f"Scraping {gid}")
            try:
                data = scraper.scrape_game(gid, info)
                db.save_game(gid, info.get("date", ""), data.get("game_type", ""), data)
            except Exception as e:
                console.print(f"[red]Error {gid}: {e}[/]")
            progress.advance(task)
            time.sleep(0.5)

    console.print(f"[green]Done! Database updated: {db_path}[/]")

if __name__ == "__main__":
    app()
