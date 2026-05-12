import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert

from sauspiel_scraper.repository import Base, GameModel, UserModel


def migrate():
    sqlite_db_path = Path("output/sauspiel.db")
    if not sqlite_db_path.exists():
        print(f"SQLite database not found at {sqlite_db_path}")
        return

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL environment variable not set")
        return

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    pg_engine = create_engine(database_url)

    # Ensure tables exist (they should if Alembic was run)
    Base.metadata.create_all(pg_engine)

    conn = sqlite3.connect(sqlite_db_path)
    cursor = conn.cursor()

    # Migrate Users
    print("Migrating users...")
    cursor.execute("SELECT username, encrypted_password, last_scraped_at FROM users")
    users = cursor.fetchall()
    with pg_engine.begin() as pg_conn:
        for username, enc_pass, last_scraped in users:
            stmt = (
                insert(UserModel)
                .values(
                    username=username, encrypted_password=enc_pass, last_scraped_at=last_scraped
                )
                .on_conflict_do_nothing()
            )
            pg_conn.execute(stmt)
    print(f"Migrated {len(users)} users.")

    # Migrate Games
    print("Migrating games...")
    cursor.execute("SELECT game_id, date, game_type, data FROM games")

    batch_size = 100
    count = 0
    while True:
        games = cursor.fetchmany(batch_size)
        if not games:
            break

        with pg_engine.begin() as pg_conn:
            for game_id, date_str, g_type, data_json in games:
                try:
                    # Parse date string back to datetime
                    # SQLite dates are stored as ISO strings
                    date_obj = datetime.fromisoformat(date_str)

                    data_dict = json.loads(data_json)

                    stmt = (
                        insert(GameModel)
                        .values(game_id=game_id, date=date_obj, game_type=g_type, data=data_dict)
                        .on_conflict_do_nothing()
                    )
                    pg_conn.execute(stmt)
                except Exception as e:
                    print(f"Error migrating game {game_id}: {e}")
            count += len(games)
            print(f"Migrated {count} games...")

    conn.close()
    print("Migration complete!")


if __name__ == "__main__":
    migrate()
