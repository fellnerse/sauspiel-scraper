import os
from pathlib import Path
from typing import Optional

from sqlalchemy import Column, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from sauspiel_scraper.models import Game

Base = declarative_base()


class GameModel(Base):
    __tablename__ = "games"

    game_id = Column(String, primary_key=True)
    date = Column(String)
    game_type = Column(String)
    data = Column(Text)


class UserModel(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True)
    encrypted_password = Column(String)
    last_scraped_at = Column(String)


class Database:
    def __init__(self, db_url: Optional[str] = None):
        if not db_url:
            # Fallback to local SQLite
            db_path = Path("output/sauspiel.db")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{db_path}"

        # Handle postgres:// vs postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_user(self, username: str, encrypted_password: str) -> None:
        with self.Session() as session:
            user = UserModel(username=username, encrypted_password=encrypted_password)
            session.merge(user)
            session.commit()

    def get_user(self, username: str) -> dict | None:
        with self.Session() as session:
            user = session.query(UserModel).filter(UserModel.username == username).first()
            if user:
                return {
                    "username": user.username,
                    "encrypted_password": user.encrypted_password,
                    "last_scraped_at": user.last_scraped_at,
                }
            return None

    def get_all_users(self) -> list[str]:
        with self.Session() as session:
            users = session.query(UserModel.username).all()
            return [u.username for u in users]

    def update_last_scraped(self, username: str, timestamp: str) -> None:
        with self.Session() as session:
            user = session.query(UserModel).filter(UserModel.username == username).first()
            if user:
                user.last_scraped_at = timestamp
                session.commit()

    def game_exists(self, game_id: str) -> bool:
        with self.Session() as session:
            return session.query(GameModel).filter(GameModel.game_id == game_id).first() is not None

    def save_game(self, game: Game) -> None:
        with self.Session() as session:
            game_obj = GameModel(
                game_id=game.game_id,
                date=game.meta.date.isoformat(),
                game_type=game.game_type or "",
                data=game.model_dump_json(exclude_unset=True),
            )
            session.merge(game_obj)
            session.commit()

    def get_all_games(self, username: str | None = None) -> list[Game]:
        with self.Session() as session:
            query = session.query(GameModel)
            if username:
                query = query.filter(GameModel.data.like(f'%"players":%"{username}"%'))
            
            rows = query.order_by(GameModel.date.desc()).all()
            games = []
            for row in rows:
                if '"error":' in row.data:
                    continue
                try:
                    games.append(Game.model_validate_json(row.data))
                except Exception:
                    continue
            return games
