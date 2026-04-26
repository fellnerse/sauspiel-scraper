import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import requests
from bs4 import BeautifulSoup, Tag

from sauspiel_scraper.models import Game, GameMeta, GamePreview, Trick
from sauspiel_scraper.rate_limiter import RateLimiter

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


class GameRepository(Protocol):
    def game_exists(self, game_id: str) -> bool: ...


class SauspielScraper:
    BASE_URL = "https://www.sauspiel.de"
    LOGIN_URL = "https://www.sauspiel.de/login"

    def __init__(
        self,
        username: str = "",
        password: str = "",
        rate_limiter: RateLimiter | None = None,
    ):
        self.username = username
        self.password = password
        self.rate_limiter = rate_limiter or RateLimiter()
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
        self._lock = threading.RLock()

    def encode_card(self, title: Any) -> str | None:
        if not title:
            return None
        t = str(title)
        return CARD_MAP.get(t, t)

    def is_logged_in(self) -> bool:
        try:
            self.rate_limiter.acquire()
            resp = self.session.get(self.BASE_URL)
            if resp.status_code == 429:
                self.rate_limiter.report_429()
                return False
            if "Ausloggen" in resp.text:
                self.rate_limiter.report_success()
                self._identify_user_id(resp.text)
                return True
        except Exception:
            pass
        return False

    def login(self) -> bool:
        with self._lock:
            # Double-check if another thread logged in while we waited for the lock
            self.rate_limiter.acquire()
            resp = self.session.get(self.BASE_URL)
            if resp.status_code == 429:
                print("DEBUG: Rate limited during login check (429)")
                self.rate_limiter.report_429()
                return False

            if "Ausloggen" in resp.text:
                self.rate_limiter.report_success()
                self._identify_user_id(resp.text)
                return True

            soup = BeautifulSoup(resp.text, "html.parser")
            token_meta = soup.find("meta", {"name": "csrf-token"})
            token = token_meta["content"] if token_meta and isinstance(token_meta, Tag) else None
            if not token:
                self.rate_limiter.acquire()
                resp = self.session.get(f"{self.BASE_URL}/login")
                if resp.status_code == 429:
                    self.rate_limiter.report_429()
                    return False
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
            self.rate_limiter.acquire()
            resp = self.session.post(f"{self.BASE_URL}/login", data=payload, allow_redirects=True)
            if resp.status_code == 429:
                self.rate_limiter.report_429()
                return False

            success = "Ausloggen" in resp.text
            if success:
                self.rate_limiter.report_success()
                self._identify_user_id(resp.text)
            else:
                print(
                    f"DEBUG: Login failed with status {resp.status_code}. "
                    f"Content length: {len(resp.text)}"
                )

            return success

    def _identify_user_id(self, html: str) -> None:
        with self._lock:
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
        with self._lock:
            return {
                "cookies": self.session.cookies.get_dict(),
                "username": self.username,
                "user_id": self.user_id,
            }

    def load_session_data(self, data: dict[str, Any]) -> None:
        with self._lock:
            self.session.cookies.update(data["cookies"])
            self.username = data.get("username", "")
            self.user_id = data.get("user_id")

    def save_session(self, file_path: Path) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(self.get_session_data(), f)

    @classmethod
    def from_session_file(cls, file_path: Path) -> SauspielScraper | None:
        if not file_path.exists():
            return None
        try:
            with open(file_path) as f:
                data = json.load(f)
            scraper = cls()
            scraper.load_session_data(data)
            if scraper.is_logged_in():
                return scraper
        except Exception:
            pass
        return None

    def get_game_list_paginated(
        self, max_new: int = 20, since: datetime | None = None, db: GameRepository | None = None
    ) -> list[GamePreview]:
        all_found: list[GamePreview] = []
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
            if self.user_id:
                params["player_id"] = self.user_id

            print(f"DEBUG: Fetching page {page} with role=all and player_id={self.user_id}...")
            # Use same-origin AJAX request style
            headers = {
                "Accept": "text/plain, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.BASE_URL}/spiele",
            }
            self.rate_limiter.acquire()
            resp = self.session.get(f"{self.BASE_URL}/spiele", params=params, headers=headers)

            if resp.status_code == 200:
                self.rate_limiter.report_success()
            elif resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                self.rate_limiter.report_429(int(retry_after) if retry_after else None)
                continue
            else:
                # Other error
                pass

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.find_all("div", class_="games-item")

            if not items:
                print(f"DEBUG: No games-item found on page {page}.")
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
                        game_meta["date"] = game_date

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
                            if "date" not in game_meta:
                                raise ValueError(f"Could not parse date for game {gid}")
                            all_found.append(GamePreview(**game_meta))
                            print(f"DEBUG: New game found: {gid}")
                        else:
                            print(f"DEBUG: Game {gid} already in DB.")

                        if new_count >= max_new and not since:
                            print(f"DEBUG: Reached max_new limit {max_new}")
                            return all_found

            # If we have 20 items, there is likely a next page (blind pagination)
            if len(items) < 20:
                print(f"DEBUG: Fewer than 20 items ({len(items)}) on page {page}, stopping.")
                break

            page += 1

        return all_found

    def scrape_game(
        self,
        game_id: str,
        preview: GamePreview,
        max_retries: int = 5,
        log_func: Any = None,
    ) -> Game:
        url = f"{self.BASE_URL}/spiele/{game_id}"
        h1 = None

        attempt = 0
        while attempt < max_retries:
            self.rate_limiter.acquire()
            resp = self.session.get(url, allow_redirects=True)

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                self.rate_limiter.report_429(int(retry_after) if retry_after else None)
                continue

            if resp.status_code != 200:
                attempt += 1
                if attempt >= max_retries:
                    raise RuntimeError(f"Failed to fetch game {game_id}: Status {resp.status_code}")
                time.sleep(1 + attempt)
                continue

            # Success!
            self.rate_limiter.report_success()
            if "Anmelden" in resp.text and "Ausloggen" not in resp.text:
                if log_func:
                    log_func(f"Session expired for {game_id}. Re-logging in...")
                if not self.login():
                    raise RuntimeError(f"Session expired and re-login failed for game {game_id}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            h1 = soup.find("h1")
            if not h1:
                if "nicht gefunden" in resp.text:
                    raise ValueError(f"Game {game_id} not found")
                attempt += 1
                if attempt >= max_retries:
                    raise RuntimeError(f"Could not find title for game {game_id}. Blocked?")
                time.sleep(1)
                continue

            # Success!
            break

        title_text = h1.get_text(strip=True) if h1 and isinstance(h1, Tag) else ""
        game_type = title_text.split()[0] if title_text else None

        players = []
        roles = {}
        klopfer = []
        initial_hands = {}
        tricks = []

        # Identify players and roles from the "Karten von" rows in the protocol
        # These divs contain both the player name and the role
        protocol_rows = soup.find_all("div", class_="card-row game-protocol-item")
        for row in protocol_rows:
            p_link = row.find("a", href=re.compile(r"^/profile/"))
            if p_link:
                pname = p_link.get_text(strip=True)
                if pname not in players:
                    players.append(pname)

                # Role is in a div inside this row
                role_el = row.find("div", class_="game-participant-role")
                if role_el:
                    roles[pname] = role_el.get_text(strip=True)

        # Initial hands (from the same rows)
        hand_rows = soup.find_all("div", id=re.compile(r"_Karten$"))
        for row in hand_rows:
            pname = str(row["id"]).replace("_Karten", "")
            cards = [
                self.encode_card(c.get("title")) or "?"
                for c in row.find_all("span", class_="card-image")
            ]
            initial_hands[pname] = cards

        # Meta results
        extra_fields = {}
        wert = None
        spielausgang = None
        laufende = None

        result_table = soup.find("table", class_="game-result-table")
        if result_table and isinstance(result_table, Tag):
            for tr in result_table.find_all("tr"):
                th, td = tr.find("th"), tr.find("td")
                if th and td:
                    key = th.get_text(strip=True).lower().replace(" ", "_")
                    val = td.get_text(strip=True)
                    if key == "klopfer":
                        klopfer = [a.get_text(strip=True) for a in td.find_all("a")]
                    elif key == "wert":
                        wert = val
                    elif key == "spielausgang":
                        spielausgang = val
                    elif key == "laufende":
                        laufende = val
                    else:
                        extra_fields[key] = val

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

            trick_winner = players.index(winner_name) if winner_name in players else None
            trick_cards = []
            for ce in card_div.select(".game-protocol-trick-card"):
                p_link = ce.find("a", class_="profile-link")
                p_name = p_link.get_text(strip=True) if p_link else None
                c_span = ce.find("span", class_="card-image")
                c_title = c_span.get("title") if c_span and isinstance(c_span, Tag) else None
                p_idx = players.index(p_name) if p_name in players else "?"
                c_code = self.encode_card(c_title) or "?"
                trick_cards.append(f"{p_idx}:{c_code}")
            tricks.append(Trick(winner=trick_winner, cards=trick_cards))

        meta = GameMeta(
            date=preview.date,
            deck_type=preview.deck_type,
            location=preview.location,
            wert=wert,
            spielausgang=spielausgang,
            laufende=laufende,
            extra_fields=extra_fields,
        )

        return Game(
            game_id=game_id,
            url=url,
            title=title_text,
            game_type=game_type,
            players=players,
            roles=roles,
            klopfer=klopfer,
            initial_hands=initial_hands,
            tricks=tricks,
            meta=meta,
        )
