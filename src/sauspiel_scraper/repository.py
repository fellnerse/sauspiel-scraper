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

    def get_all_games(self) -> list[Game]:
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
