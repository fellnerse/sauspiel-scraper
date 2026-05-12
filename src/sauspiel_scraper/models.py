import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class GameResult(StrEnum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


class Trick(BaseModel):
    winner: int | None = Field(default=None, description="Index of the player in the players list")
    cards: list[str] = Field(
        default_factory=list, description="List of cards in the trick (e.g. '0:E-A')"
    )


class GameMeta(BaseModel):
    date: datetime
    deck_type: str | None = None
    location: str | None = None
    wert: str | None = None
    spielausgang: str | None = None
    laufende: str | None = None
    # Catch-all for any other parsed meta fields from the HTML table
    extra_fields: dict[str, str] = Field(default_factory=dict)

    @property
    def value_int(self) -> int:
        """Parses the 'wert' string into an integer (cents)."""
        if not self.wert:
            return 0
        try:
            return int(re.sub(r"[^\d-]", "", self.wert))
        except (ValueError, TypeError):
            return 0

    @property
    def is_won(self) -> bool:
        """Returns True if the game was won."""
        return "gewonnen" in (self.spielausgang or "").lower()

    @property
    def laufende_int(self) -> int:
        """Parses the 'laufende' string into an integer."""
        if not self.laufende:
            return 0
        try:
            return int(re.sub(r"[^\d]", "", self.laufende))
        except (ValueError, TypeError):
            return 0


class Game(BaseModel):
    game_id: str
    url: str | None = None
    title: str | None = None
    game_type: str | None = None
    players: list[str] = Field(default_factory=list)
    roles: dict[str, str] = Field(default_factory=dict)
    klopfer: list[str] = Field(default_factory=list)
    initial_hands: dict[str, list[str]] = Field(default_factory=dict)
    tricks: list[Trick] = Field(default_factory=list)
    meta: GameMeta


class GamePreview(BaseModel):
    game_id: str
    date: datetime
    deck_type: str | None = None
    location: str | None = None


class ProcessedGame(BaseModel):
    game_id: str
    date: datetime
    game_type: str
    declarer: str
    role: str
    declarer_result: GameResult
    my_result: GameResult
    net_profit_cents: int
    laufende: int
    location: str
