from datetime import datetime

from pydantic import BaseModel, Field


class Trick(BaseModel):
    winner: int | None = Field(default=None)
    cards: list[str] = Field(default_factory=list)

class GameMeta(BaseModel):
    date: datetime
    deck_type: str | None = None

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

json_data = '{"game_id": "123", "error": "Not found", "meta": {"date": "2024-03-20T12:00:00"}}'
try:
    g = Game.model_validate_json(json_data)
    print("Parsed!")
    print(g.model_dump())
except Exception as e:
    print("Error:", e)
