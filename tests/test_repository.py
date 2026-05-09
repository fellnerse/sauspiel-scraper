from datetime import datetime

from sauspiel_scraper.models import Game, GameMeta
from sauspiel_scraper.repository import Database, GameModel


def test_database_save_and_get(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    game = Game(game_id="123", meta=GameMeta(date=datetime(2024, 1, 1, 12, 0)))
    db.save_game(game)

    assert db.game_exists("123")

    games = db.get_all_games()
    assert len(games) == 1
    assert games[0].game_id == "123"


def test_database_get_all_games_ignores_invalid(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)

    # Insert invalid data directly
    with db.session_scope() as session:
        session.add_all(
            [
                GameModel(
                    game_id="invalid1",
                    date=datetime(2024, 1, 1),
                    game_type="",
                    data={"error": "Not found", "meta": {"date": "2024-01-01T12:00:00"}},
                ),
                GameModel(
                    game_id="invalid2",
                    date=datetime(2024, 1, 1),
                    game_type="",
                    data={"garbage": "data"},
                ),
            ]
        )

    # Should skip invalid records and return empty list
    games = db.get_all_games()
    assert len(games) == 0
