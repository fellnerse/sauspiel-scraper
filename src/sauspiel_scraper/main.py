import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Optional

import requests
import typer
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

# Load .env if it exists
load_dotenv()

app = typer.Typer(help="Sauspiel Game Scraper CLI")
console = Console()

CARD_MAP = {
    "Eichel-Sau": "E-A",
    "Die Alte": "E-A",
    "Eichel-Zehn": "E-X",
    "Eichel-König": "E-K",
    "Eichel-Ober": "E-O",
    "Der Alte": "E-O",
    "Eichel-Unter": "E-U",
    "Eichel-Neun": "E-9",
    "Eichel-Acht": "E-8",
    "Eichel-Sieben": "E-7",
    "Gras-Sau": "G-A",
    "Die Blaue": "G-A",
    "Gras-Zehn": "G-X",
    "Gras-König": "G-K",
    "Gras-Ober": "G-O",
    "Der Blaue": "G-O",
    "Gras-Unter": "G-U",
    "Gras-Neun": "G-9",
    "Gras-Acht": "G-8",
    "Gras-Sieben": "G-7",
    "Herz-Sau": "H-A",
    "Herz-Zehn": "H-X",
    "Herz-König": "H-K",
    "Herz-Ober": "H-O",
    "Der Rote": "H-O",
    "Herz-Unter": "H-U",
    "Herz-Neun": "H-9",
    "Herz-Acht": "H-8",
    "Herz-Sieben": "H-7",
    "Schellen-Sau": "S-A",
    "Die Hundsgfickte": "S-A",
    "Schellen-Zehn": "S-X",
    "Schellen-König": "S-K",
    "Schellen-Ober": "S-O",
    "Der Runde": "S-O",
    "Schellen-Unter": "S-U",
    "Schellen-Neun": "S-9",
    "Schellen-Acht": "S-8",
    "Schellen-Sieben": "S-7",
}


class SauspielScraper:
    BASE_URL = "https://www.sauspiel.de"
    LOGIN_URL = f"{BASE_URL}/login"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )
        self.user_id: str | None = None

    def encode_card(self, title: Any) -> str | None:
        if not title:
            return None
        t = str(title)
        return CARD_MAP.get(t, t)

    def login(self) -> bool:
        resp = self.session.get(self.BASE_URL)
        if "Ausloggen" in resp.text:
            self._identify_user_id(resp.text)
            return True

        soup = BeautifulSoup(resp.text, "html.parser")
        token_meta = soup.find("meta", {"name": "csrf-token"})
        token = token_meta["content"] if token_meta and isinstance(token_meta, Tag) else None

        if not token:
            resp = self.session.get(self.LOGIN_URL)
            soup = BeautifulSoup(resp.text, "html.parser")
            token_input = soup.find("input", {"name": "authenticity_token"})
            token = (
                token_input["value"] if token_input and isinstance(token_input, Tag) else None
            )

        payload = {
            "utf8": "✓",
            "authenticity_token": token,
            "login": self.username,
            "password": self.password,
            "remember_me": "1",
            "commit": "Anmelden",
        }
        resp = self.session.post(self.LOGIN_URL, data=payload, allow_redirects=True)
        success = "Ausloggen" in resp.text
        if success:
            self._identify_user_id(resp.text)
        return success

    def _identify_user_id(self, html: str) -> None:
        soup = BeautifulSoup(html, "html.parser")
        # Try finding the specific profile link with data-username
        me_link = soup.find("a", attrs={"data-username": self.username})
        
        if not me_link:
            # Fallback: check all links for username in text
            for a in soup.find_all("a", href=re.compile(r"^/profile/")):
                if self.username.lower() in a.get_text().lower():
                    me_link = a
                    break

        if me_link and isinstance(me_link, Tag) and me_link.has_attr("data-userid"):
            self.user_id = str(me_link["data-userid"])
        else:
            # Last ditch effort: search for data-userid anywhere in the HTML near username
            match = re.search(rf'data-userid="(\d+)"[^>]*>{self.username}', html, re.I)
            if match:
                self.user_id = match.group(1)

        if self.user_id:
            console.print(f"[dim]Identified User ID: {self.user_id}[/]")
        else:
            console.print("[bold red]Warning: Could not identify User ID. History might be empty.[/]")

    def get_game_list(
        self, limit: int | None = 10, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        if not self.user_id:
            return []

        games: list[dict[str, Any]] = []
        page = 1

        while True:
            url = f"{self.BASE_URL}/spiele?player_id={self.user_id}&page={page}"
            resp = self.session.get(url)
            soup = BeautifulSoup(resp.text, "html.parser")

            items = soup.find_all("div", class_="games-item")
            if not items:
                break

            for item in items:
                game_meta: dict[str, Any] = {}
                subtext = item.find("p", class_="card-title-subtext")
                if subtext:
                    txt = subtext.get_text()
                    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4}\s\d{2}:\d{2})", txt)
                    if date_match:
                        game_date = datetime.strptime(date_match.group(1), "%d.%m.%Y %H:%M")
                        if since and game_date < since:
                            return games
                        game_meta["date"] = game_date.isoformat()

                    parts = [p.strip() for p in txt.split("—")]
                    if len(parts) >= 2:
                        game_meta["deck_type"] = parts[-1]
                        loc_part = parts[0].split(",")[-1].strip() if "," in parts[0] else None
                        if loc_part:
                            game_meta["location"] = loc_part

                h4 = item.find("h4", class_="card-title")
                link = h4.find("a") if h4 and isinstance(h4, Tag) else None
                if link and isinstance(link, Tag):
                    href = str(link.get("href", ""))
                    match = re.search(r"/spiele/(\d+)", href)
                    if match:
                        gid = match.group(1)
                        if gid not in [g["game_id"] for g in games]:
                            game_meta["game_id"] = gid
                            games.append(game_meta)

                if limit and len(games) >= limit:
                    return games

            next_link = soup.find("a", class_="next_page")
            if not next_link:
                break
            page += 1

        return games

    def scrape_game(self, game_id: str, list_meta: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.BASE_URL}/spiele/{game_id}"
        resp = self.session.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        h1 = soup.find("h1")
        game_data: dict[str, Any] = {
            "game_id": game_id,
            "url": url,
            "title": h1.get_text(strip=True) if h1 and isinstance(h1, Tag) else None,
            "players": [],
            "klopfer": [],
            "initial_hands": {},
            "tricks": [],
            "meta": list_meta.copy(),
        }

        if game_data["title"]:
            game_data["game_type"] = game_data["title"].split()[0]

        hand_rows = soup.find_all("div", id=re.compile(r"_Karten$"))
        for row in hand_rows:
            pname = str(row["id"]).replace("_Karten", "")
            if pname not in game_data["players"]:
                game_data["players"].append(pname)
            cards = [
                self.encode_card(c.get("title")) for c in row.find_all("span", class_="card-image")
            ]
            game_data["initial_hands"][pname] = cards

        result_table = soup.find("table", class_="game-result-table")
        if result_table and isinstance(result_table, Tag):
            for tr in result_table.find_all("tr"):
                th = tr.find("th")
                td = tr.find("td")
                if th and td:
                    key = th.get_text(strip=True).lower().replace(" ", "_")
                    if key == "klopfer":
                        game_data["klopfer"] = [a.get_text(strip=True) for a in td.find_all("a")]
                    else:
                        game_data["meta"][key] = td.get_text(strip=True)

        trick_headers = soup.find_all("h4", class_="card-title")
        for header in trick_headers:
            header_text = header.get_text(strip=True)
            if not re.search(r"\d+\. Stich", header_text):
                continue

            card_div = header.find_parent("div", class_="card")
            if not card_div:
                continue
            winner_div = card_div.find("div", class_="game-participant-avatar")
            winner_a = winner_div.find("a") if winner_div and isinstance(winner_div, Tag) else None
            winner_name = (
                str(winner_a["data-username"]) if winner_a and isinstance(winner_a, Tag) else None
            )

            trick_data: dict[str, Any] = {
                "winner": (
                    game_data["players"].index(winner_name)
                    if winner_name in game_data["players"]
                    else None
                ),
                "cards": [],
            }

            for ce in card_div.select(".game-protocol-trick-card"):
                p_link = ce.find("a", class_="profile-link")
                p_name = p_link.get_text(strip=True) if p_link else None
                c_span = ce.find("span", class_="card-image")
                c_title = c_span.get("title") if c_span and isinstance(c_span, Tag) else None

                p_idx = (
                    game_data["players"].index(p_name) if p_name in game_data["players"] else "?"
                )
                c_code = self.encode_card(c_title) or "?"
                trick_data["cards"].append(f"{p_idx}:{c_code}")

            game_data["tricks"].append(trick_data)

        return game_data


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
            for game_info in game_list:
                gid = game_info["game_id"]
                progress.update(task, description=f"[cyan]Scraping Game {gid}...")

                try:
                    game_data = scraper.scrape_game(gid, game_info)
                    if pretty:
                        results.append(game_data)
                    else:
                        assert f is not None
                        f.write(json.dumps(game_data, ensure_ascii=False) + "\n")
                        f.flush()

                except Exception as e:
                    console.print(f"[red]Error scraping game {gid}: {e}[/]")

                progress.advance(task)
                time.sleep(0.5)
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
        str(len(results) if pretty else len(game_list)),
        str(output),
        "JSON (Pretty)" if pretty else "JSONL",
    )
    console.print(table)


if __name__ == "__main__":
    app()
