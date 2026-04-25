from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Trick(BaseModel):
    winner: int | None = Field(default=None, description="Index of the player in the players list")
    cards: list[str] = Field(default_factory=list, description="List of cards in the trick (e.g. '0:E-A')")


class GameMeta(BaseModel):
    date: datetime
    deck_type: str | None = None
    location: str | None = None
    wert: str | None = None
    spielausgang: str | None = None
    laufende: str | None = None
    # Catch-all for any other parsed meta fields from the HTML table
    extra_fields: dict[str, str] = Field(default_factory=dict)


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
