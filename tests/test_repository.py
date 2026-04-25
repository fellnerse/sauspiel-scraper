from datetime import datetime

from sauspiel_scraper.models import Game, GameMeta
from sauspiel_scraper.repository import Database


def test_database_save_and_get(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    game = Game(
        game_id="123",
        meta=GameMeta(date=datetime(2024, 1, 1, 12, 0))
    )
    db.save_game(game)
    
    assert db.game_exists("123")
    
    games = db.get_all_games()
    assert len(games) == 1
    assert games[0].game_id == "123"

def test_database_get_all_games_ignores_invalid(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Insert invalid data directly
    db.conn.execute(
        "INSERT INTO games (game_id, date, game_type, data) VALUES (?, ?, ?, ?)",
        ("invalid1", "2024-01-01", "", '{"error": "Not found", "meta": {"date": "2024-01-01T12:00:00"}}')
    )
    db.conn.execute(
        "INSERT INTO games (game_id, date, game_type, data) VALUES (?, ?, ?, ?)",
        ("invalid2", "2024-01-01", "", '{"garbage": "data"}')
    )
    db.conn.commit()
    
    # Should skip invalid records and return empty list
    games = db.get_all_games()
    assert len(games) == 0
