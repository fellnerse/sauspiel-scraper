import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

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


class Database:
    def __init__(self, db_path: Path = Path("output/sauspiel.db")):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                date TEXT,
                game_type TEXT,
                data TEXT
            )
        """)
        self.conn.commit()

    def game_exists(self, game_id: str) -> bool:
        cursor = self.conn.execute("SELECT 1 FROM games WHERE game_id = ?", (game_id,))
        return cursor.fetchone() is not None

    def save_game(self, game_id: str, date: str, game_type: str, data: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO games (game_id, date, game_type, data) VALUES (?, ?, ?, ?)",
            (game_id, date, game_type, json.dumps(data, ensure_ascii=False)),
        )
        self.conn.commit()

    def get_all_games(self) -> list[dict[str, Any]]:
        cursor = self.conn.execute("SELECT data FROM games ORDER BY date DESC")
        return [json.loads(row[0]) for row in cursor.fetchall()]


class SauspielScraper:
    BASE_URL = "https://www.sauspiel.de"
    LOGIN_URL = f"{BASE_URL}/login"

    def __init__(self, username: str = "", password: str = ""):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )
        self.user_id: str | None = None

    def encode_card(self, title: Any) -> str | None:
        if not title:
            return None
        t = str(title)
        return CARD_MAP.get(t, t)

    def is_logged_in(self) -> bool:
        try:
            resp = self.session.get(self.BASE_URL)
            if "Ausloggen" in resp.text:
                self._identify_user_id(resp.text)
                return True
        except Exception:
            pass
        return False

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
        if not self.username:
            user_el = soup.find("span", class_="topbar-username-mobile")
            if user_el:
                self.username = user_el.get_text().strip()

        me_link = soup.find("a", attrs={"data-username": self.username})
        if not me_link:
            for a in soup.find_all("a", href=re.compile(r"^/profile/")):
                if self.username.lower() in a.get_text().lower():
                    me_link = a
                    break

        if me_link and isinstance(me_link, Tag) and me_link.has_attr("data-userid"):
            self.user_id = str(me_link["data-userid"])
        else:
            match = re.search(rf'data-userid="(\d+)"[^>]*>{self.username}', html, re.I)
            if match:
                self.user_id = match.group(1)

    def get_session_data(self) -> dict[str, Any]:
        return {
            "cookies": self.session.cookies.get_dict(),
            "username": self.username,
            "user_id": self.user_id,
        }

    def load_session_data(self, data: dict[str, Any]) -> None:
        self.session.cookies.update(data["cookies"])
        self.username = data.get("username", "")
        self.user_id = data.get("user_id")

    def get_game_list_paginated(
        self, max_new: int = 20, since: datetime | None = None, db: Database | None = None
    ) -> list[dict[str, Any]]:
        all_found: list[dict[str, Any]] = []
        new_count = 0
        page = 1

        while True:
            params = {
                "utf8": "✓",
                "user[login]": "",
                "role": "all",
                "game[balance_type]": "-1",
                "game[short_deck]": "-1",
                "game[game_type_id]": "-1",
                "game[announcement]": "-1",
                "game[contras]": "-1",
                "game[runners_from]": "-14",
                "game[runners_to]": "14",
                "game[won]": "-1",
                "game[result]": "-1",
                "page": page,
            }

            print(f"DEBUG: Fetching page {page} with role=all...")
            resp = self.session.get(f"{self.BASE_URL}/spiele", params=params)
            soup = BeautifulSoup(resp.text, "html.parser")

            # Exhaustive debug for links
            page_links = soup.find_all("a", href=re.compile(r"page="))
            if page_links:
                print(f"DEBUG: Found {len(page_links)} links with 'page=' in href.")
                for l in page_links:
                    print(f"DEBUG: Link: {l.get('href')} | Text: {l.get_text(strip=True)}")

            items = soup.find_all("div", class_="games-item")

            if not items:
                all_divs = soup.find_all("div")
                print(
                    f"DEBUG: No games-item found on page {page}. Found {len(all_divs)} total divs."
                )
                if len(resp.text) < 500:
                    print(f"DEBUG: Response text: {resp.text}")
                else:
                    print(f"DEBUG: Response snippet: {resp.text[:500]}...")
                break

            print(f"DEBUG: Found {len(items)} items on page {page}.")
            for item in items:
                game_meta: dict[str, Any] = {}
                subtext = item.find("p", class_="card-title-subtext")
                if subtext:
                    txt = subtext.get_text()
                    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4}\s\d{2}:\d{2})", txt)
                    if date_match:
                        game_date = datetime.strptime(date_match.group(1), "%d.%m.%Y %H:%M")
                        if since and game_date < since:
                            print(f"DEBUG: Reached date threshold {since}")
                            return all_found
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
                        game_meta["game_id"] = gid

                        exists = db.game_exists(gid) if db else False
                        if not exists:
                            new_count += 1
                            all_found.append(game_meta)
                            print(f"DEBUG: New game found: {gid}")
                        else:
                            print(f"DEBUG: Game {gid} already in DB.")

                        if new_count >= max_new and not since:
                            print(f"DEBUG: Reached max_new limit {max_new}")
                            return all_found

            next_link = (
                soup.find("a", class_="next_page")
                or soup.find("a", rel="next")
                or soup.find("a", href=re.compile(f"page={page + 1}"))
            )
            if not next_link:
                pagination = soup.find("div", class_="pagination")
                if pagination:
                    print(
                        f"DEBUG: Pagination found but no next link: "
                        f"{pagination.get_text(strip=True)}"
                    )
                else:
                    print("DEBUG: No pagination div or next link found.")
                break
            page += 1

        return all_found

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
            "roles": {},
            "klopfer": [],
            "initial_hands": {},
            "tricks": [],
            "meta": list_meta.copy(),
        }

        if game_data["title"]:
            game_data["game_type"] = game_data["title"].split()[0]

        # Identify players and roles from the "Karten von" rows in the protocol
        # These divs contain both the player name and the role
        protocol_rows = soup.find_all("div", class_="card-row game-protocol-item")
        for row in protocol_rows:
            p_link = row.find("a", href=re.compile(r"^/profile/"))
            if p_link:
                pname = p_link.get_text(strip=True)
                if pname not in game_data["players"]:
                    game_data["players"].append(pname)

                # Role is in a div inside this row
                role_el = row.find("div", class_="game-participant-role")
                if role_el:
                    game_data["roles"][pname] = role_el.get_text(strip=True)

        # Initial hands (from the same rows)
        hand_rows = soup.find_all("div", id=re.compile(r"_Karten$"))
        for row in hand_rows:
            pname = str(row["id"]).replace("_Karten", "")
            cards = [
                self.encode_card(c.get("title")) for c in row.find_all("span", class_="card-image")
            ]
            game_data["initial_hands"][pname] = cards

        # Meta results
        result_table = soup.find("table", class_="game-result-table")
        if result_table and isinstance(result_table, Tag):
            for tr in result_table.find_all("tr"):
                th, td = tr.find("th"), tr.find("td")
                if th and td:
                    key = th.get_text(strip=True).lower().replace(" ", "_")
                    if key == "klopfer":
                        game_data["klopfer"] = [a.get_text(strip=True) for a in td.find_all("a")]
                    else:
                        game_data["meta"][key] = td.get_text(strip=True)

        # Tricks
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
