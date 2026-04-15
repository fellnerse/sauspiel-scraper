import json
import re
import time
from pathlib import Path
from typing import Annotated, Any

import requests
import typer
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv

# Load .env if it exists
load_dotenv()

app = typer.Typer(help="Sauspiel Game Scraper CLI")

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
            token = token_input["value"] if token_input and isinstance(token_input, Tag) else None

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
        me_link = soup.find("a", href=re.compile(r"^/profile/"))
        if me_link and isinstance(me_link, Tag) and me_link.has_attr("data-userid"):
            self.user_id = str(me_link["data-userid"])
        else:
            self.user_id = "313407"

    def get_game_list(self, limit: int = 10) -> list[str]:
        url = f"{self.BASE_URL}/spiele?player_id={self.user_id}"
        resp = self.session.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        game_ids: list[str] = []
        links = soup.find_all("a", href=re.compile(r"^/spiele/\d+"))
        for link in links:
            href = str(link.get("href", ""))
            match = re.search(r"/spiele/(\d+)", href)
            if match:
                gid = match.group(1)
                if gid not in game_ids:
                    game_ids.append(gid)
            if len(game_ids) >= limit:
                break
        return game_ids

    def scrape_game(self, game_id: str) -> dict[str, Any]:
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
            "meta": {},
        }

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

        # Using class_ instead of string to avoid overload issues with ty/bs4 types
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
            winner_name = str(winner_a["data-username"]) if winner_a and isinstance(winner_a, Tag) else None

            trick_data: dict[str, Any] = {
                "winner_index": (
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
                trick_data["cards"].append(
                    {
                        "player_index": (
                            game_data["players"].index(p_name)
                            if p_name in game_data["players"]
                            else None
                        ),
                        "card": self.encode_card(c_title),
                    }
                )
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
    count: Annotated[int, typer.Option("--count", "-c", help="Number of games to scrape")] = 5,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output JSON file path")
    ] = Path("output/games.json"),
) -> None:
    """
    Scrape recent games from sauspiel.de.
    """
    # Ensure output directory exists
    output.parent.mkdir(parents=True, exist_ok=True)

    scraper = SauspielScraper(username, password)

    typer.echo(f"Logging in as {username}...")
    if not scraper.login():
        typer.echo("Login failed. Check your credentials.", err=True)
        raise typer.Exit(1)

    typer.echo("Fetching game list...")
    game_ids = scraper.get_game_list(limit=count)
    if not game_ids:
        typer.echo("No games found.")
        return

    typer.echo(f"Found {len(game_ids)} games. Starting scrape...")
    results = []
    with typer.progressbar(game_ids, label="Scraping") as progress:
        for gid in progress:
            results.append(scraper.scrape_game(gid))
            time.sleep(1)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    typer.echo(f"Successfully saved {len(results)} games to {output}")


if __name__ == "__main__":
    app()
