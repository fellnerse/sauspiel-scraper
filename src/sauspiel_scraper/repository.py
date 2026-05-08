import sqlite3
import threading
from pathlib import Path

from sauspiel_scraper.models import Game


class Database:
    def __init__(self, db_path: Path = Path("output/sauspiel.db")):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self) -> None:
        with self._lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    game_id TEXT PRIMARY KEY,
                    date TEXT,
                    game_type TEXT,
                    data TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    encrypted_password TEXT,
                    last_scraped_at TEXT
                )
            """)
            self.conn.commit()

    def save_user(self, username: str, encrypted_password: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO users (username, encrypted_password) VALUES (?, ?)",
                (username, encrypted_password),
            )
            self.conn.commit()

    def get_user(self, username: str) -> dict | None:
        cursor = self.conn.execute(
            "SELECT username, encrypted_password, last_scraped_at FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "username": row[0],
                "encrypted_password": row[1],
                "last_scraped_at": row[2],
            }
        return None

    def get_all_users(self) -> list[str]:
        cursor = self.conn.execute("SELECT username FROM users")
        return [row[0] for row in cursor.fetchall()]

    def update_last_scraped(self, username: str, timestamp: str) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE users SET last_scraped_at = ? WHERE username = ?",
                (timestamp, username),
            )
            self.conn.commit()

    def game_exists(self, game_id: str) -> bool:
        # SELECT is generally safe without a lock in WAL mode or if we don't mind stale reads,
        # but for consistency we could also lock here. Given the plan, we'll keep it light.
        cursor = self.conn.execute("SELECT 1 FROM games WHERE game_id = ?", (game_id,))
        return cursor.fetchone() is not None

    def save_game(self, game: Game) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO games (game_id, date, game_type, data) VALUES (?, ?, ?, ?)",
                (
                    game.game_id,
                    game.meta.date.isoformat(),
                    game.game_type or "",
                    game.model_dump_json(exclude_unset=True),
                ),
            )
            self.conn.commit()

    def get_all_games(self, username: str | None = None) -> list[Game]:
        if username:
            # We use a LIKE query to filter games where the user is one of the players.
            # In the JSON blob, the players list looks like "players":["user1","user2",...]
            # Using "%"username"%" helps ensure we match the full username.
            cursor = self.conn.execute(
                "SELECT data FROM games WHERE data LIKE ? ORDER BY date DESC",
                (f'%"players":%"{username}"%',),
            )
        else:
            cursor = self.conn.execute("SELECT data FROM games ORDER BY date DESC")
        games = []
        for row in cursor.fetchall():
            if '"error":' in row[0]:
                continue
            try:
                games.append(Game.model_validate_json(row[0]))
            except Exception:
                # Graceful fallback: ignore invalid historical rows as specified in the plan
                continue
        return games
