import os
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, create_engine, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from sauspiel_scraper.models import Game


class Base(DeclarativeBase):
    pass


class GameModel(Base):
    __tablename__ = "games"

    game_id: Mapped[str] = mapped_column(primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    game_type: Mapped[str] = mapped_column(String)
    # Use JSON with JSONB variant for PostgreSQL
    data: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"))

    __table_args__ = (
        Index(
            "idx_games_data_players",
            data["players"],
            postgresql_using="gin",
        ),
    )


class UserModel(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(primary_key=True)
    encrypted_password: Mapped[str] = mapped_column(String)
    last_scraped_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Database:
    def __init__(self, db_path: Path = Path("output/sauspiel.db")):
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            # Sanitize URL for SQLAlchemy 2.0
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            self.engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_recycle=300,
            )
        else:
            # Fallback to local SQLite
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.engine = create_engine(f"sqlite:///{db_path}")

        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

        # Only use create_all for local SQLite fallback or if specifically needed.
        # Production should use Alembic.
        if not os.environ.get("DATABASE_URL"):
            Base.metadata.create_all(self.engine)

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def save_user(
        self, username: str, encrypted_password: str, session: Session | None = None
    ) -> None:
        if session is None:
            with self.session_scope() as session:
                self._save_user(username, encrypted_password, session)
        else:
            self._save_user(username, encrypted_password, session)

    def _save_user(self, username: str, encrypted_password: str, session: Session) -> None:
        user = session.get(UserModel, username)
        if user:
            user.encrypted_password = encrypted_password
        else:
            session.add(UserModel(username=username, encrypted_password=encrypted_password))

    def get_user(self, username: str, session: Session | None = None) -> dict | None:
        if session is None:
            with self.Session() as session:
                return self._get_user(username, session)
        return self._get_user(username, session)

    def _get_user(self, username: str, session: Session) -> dict | None:
        user = session.get(UserModel, username)
        if user:
            return {
                "username": user.username,
                "encrypted_password": user.encrypted_password,
                "last_scraped_at": user.last_scraped_at,
            }
        return None

    def get_all_users(self, session: Session | None = None) -> list[str]:
        if session is None:
            with self.Session() as session:
                return self._get_all_users(session)
        return self._get_all_users(session)

    def _get_all_users(self, session: Session) -> list[str]:
        result = session.execute(select(UserModel.username))
        return [row[0] for row in result.fetchall()]

    def update_last_scraped(
        self, username: str, timestamp: str, session: Session | None = None
    ) -> None:
        if session is None:
            with self.session_scope() as session:
                self._update_last_scraped(username, timestamp, session)
        else:
            self._update_last_scraped(username, timestamp, session)

    def _update_last_scraped(self, username: str, timestamp: str, session: Session) -> None:
        session.execute(
            update(UserModel)
            .where(UserModel.username == username)
            .values(last_scraped_at=timestamp)
        )

    def game_exists(self, game_id: str, session: Session | None = None) -> bool:
        if session is None:
            with self.Session() as session:
                return self._game_exists(game_id, session)
        return self._game_exists(game_id, session)

    def _game_exists(self, game_id: str, session: Session) -> bool:
        return session.get(GameModel, game_id) is not None

    def save_game(self, game: Game, session: Session | None = None) -> None:
        if session is None:
            with self.session_scope() as session:
                self._save_game(game, session)
        else:
            self._save_game(game, session)

    def _save_game(self, game: Game, session: Session) -> None:
        existing = session.get(GameModel, game.game_id)
        if existing:
            existing.date = game.meta.date
            existing.game_type = game.game_type or ""
            existing.data = game.model_dump(mode="json", exclude_unset=True)
        else:
            session.add(
                GameModel(
                    game_id=game.game_id,
                    date=game.meta.date,
                    game_type=game.game_type or "",
                    data=game.model_dump(mode="json", exclude_unset=True),
                )
            )

    def get_all_games(
        self, username: str | None = None, session: Session | None = None
    ) -> list[Game]:
        if session is None:
            with self.Session() as session:
                return self._get_all_games(username, session)
        return self._get_all_games(username, session)

    def _get_all_games(self, username: str | None, session: Session) -> list[Game]:
        stmt = select(GameModel).order_by(GameModel.date.desc())
        if username:
            if self.engine.dialect.name == "postgresql":
                # Ensure we use JSONB containment operator @>
                stmt = stmt.where(GameModel.data["players"].cast(JSONB).contains([username]))
            else:
                # SQLite fallback using LIKE
                stmt = stmt.where(GameModel.data.cast(String).like(f'%"players":%"{username}"%'))

        result = session.execute(stmt)
        games = []
        for row in result.scalars():
            data = row.data
            if "error" in data:
                continue
            try:
                # SQLAlchemy automatically deserializes JSON columns
                games.append(Game.model_validate(data))
            except Exception:
                continue
        return games
