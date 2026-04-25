from datetime import datetime

from pydantic import BaseModel, Field


class GameMeta(BaseModel):
    date: datetime
    deck_type: str | None = None
    extra_fields: dict[str, str] = Field(default_factory=dict)

class Game(BaseModel):
    meta: GameMeta

json_data = '{"meta": {"date": "2024-03-20T12:00:00", "deck_type": "Kurze", "some_random_old_field": "foo"}}'
try:
    g = Game.model_validate_json(json_data)
    print("Parsed!")
    print(g.meta.model_dump())
except Exception as e:
    print("Error:", e)
