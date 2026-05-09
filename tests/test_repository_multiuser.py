from datetime import datetime

import pytest

from sauspiel_scraper.models import Game, GameMeta
from sauspiel_scraper.repository import Database


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    return Database(db_path)


def test_users_table_created(db):
    cursor = db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    assert cursor.fetchone() is not None


def test_users_table_schema(db):
    cursor = db.conn.execute("PRAGMA table_info(users)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert "username" in columns
    assert "encrypted_password" in columns
    assert "last_scraped_at" in columns
    assert columns["username"] == "TEXT"
    assert columns["encrypted_password"] == "TEXT"
    assert columns["last_scraped_at"] == "TEXT"


def test_save_and_get_user(db):
    db.save_user("testuser", "hashed_pw")
    user = db.get_user("testuser")
    assert user["username"] == "testuser"
    assert user["encrypted_password"] == "hashed_pw"
    assert user["last_scraped_at"] is None


def test_get_all_users(db):
    db.save_user("user1", "pw1")
    db.save_user("user2", "pw2")
    users = db.get_all_users()
    assert set(users) == {"user1", "user2"}


def test_update_last_scraped(db):
    db.save_user("testuser", "pw")
    now = datetime.now().isoformat()
    db.update_last_scraped("testuser", now)
    user = db.get_user("testuser")
    assert user["last_scraped_at"] == now


def test_get_all_games_filtered_by_username(db):
    # Create two games, one with 'user1' and one with 'user2'
    game1 = Game(
        game_id="1",
        players=["user1", "other1", "other2", "other3"],
        meta=GameMeta(date=datetime.now()),
    )
    game2 = Game(
        game_id="2",
        players=["user2", "other1", "other2", "other4"],
        meta=GameMeta(date=datetime.now()),
    )
    db.save_game(game1)
    db.save_game(game2)

    user1_games = db.get_all_games(username="user1")
    assert len(user1_games) == 1
    assert user1_games[0].game_id == "1"

    user2_games = db.get_all_games(username="user2")
    assert len(user2_games) == 1
    assert user2_games[0].game_id == "2"

    all_games = db.get_all_games()
    assert len(all_games) == 2
