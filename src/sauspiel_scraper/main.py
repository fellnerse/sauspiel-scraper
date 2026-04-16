import json
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from sauspiel_scraper.core import SauspielScraper, scrape_games_stream

app = typer.Typer(help="Sauspiel Game Scraper CLI")
console = Console()


@app.command()
def scrape(
    username: Annotated[
        str,
        typer.Option("--username", "-u", envvar="USERNAME", prompt=True, help="Sauspiel username"),
    ],
    password: Annotated[
        str,
        typer.Option(
            "--password",
            "-p",
            envvar="PASSWORD",
            prompt=True,
            hide_input=True,
            help="Sauspiel password",
        ),
    ],
    count: Annotated[
        Optional[int], typer.Option("--count", "-c", help="Number of games to scrape")
    ] = None,
    since: Annotated[
        Optional[str],
        typer.Option("--since", "-s", help="Scrape games since date (DD.MM.YYYY)"),
    ] = None,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output file path")
    ] = Path("output/games.jsonl"),
    pretty: Annotated[
        bool, typer.Option("--pretty", help="Save as a single pretty-printed JSON array")
    ] = False,
) -> None:
    """
    Scrape recent games from sauspiel.de.
    """
    if count is None and since is None:
        count = 5

    since_dt = None
    if since:
        try:
            since_dt = datetime.strptime(since, "%d.%m.%Y")
        except ValueError:
            console.print("[bold red]Error: Invalid date format for --since. Use DD.MM.YYYY[/]")
            raise typer.Exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    scraper = SauspielScraper(username, password)

    with console.status(f"[bold green]Logging in as {username}...", spinner="dots"):
        if not scraper.login():
            console.print("[bold red]Login failed. Check your credentials.[/]")
            raise typer.Exit(1)

    with console.status("[bold blue]Fetching game list...", spinner="dots"):
        game_list = scraper.get_game_list(limit=count, since=since_dt)

    if not game_list:
        console.print("[yellow]No games found for your user ID.[/]")
        return

    console.print(f"[bold green]Found {len(game_list)} games. Starting scrape...[/]")

    results = []
    success_count = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Scraping...", total=len(game_list))

        f = None if pretty else open(output, "w", encoding="utf-8")

        try:
            for game_data in scrape_games_stream(scraper, limit=count, since=since_dt):
                gid = game_data["game_id"]
                progress.update(task, description=f"[cyan]Scraping Game {gid}...")

                if pretty:
                    results.append(game_data)
                else:
                    assert f is not None
                    f.write(json.dumps(game_data, ensure_ascii=False) + "\n")
                    f.flush()

                success_count += 1
                progress.advance(task)
                time.sleep(0.5)
        except Exception as e:
            console.print(f"[red]Error during scraping: {e}[/]")
        finally:
            if f:
                f.close()

    if pretty:
        with open(output, "w", encoding="utf-8") as f_out:
            json.dump(results, f_out, ensure_ascii=False, indent=2)

    table = Table(title="Scraping Summary")
    table.add_column("Games Scraped", justify="right", style="cyan")
    table.add_column("Output File", style="magenta")
    table.add_column("Format", style="green")
    table.add_row(
        str(success_count),
        str(output),
        "JSON (Pretty)" if pretty else "JSONL",
    )
    console.print(table)


if __name__ == "__main__":
    app()
