import re

import pandas as pd

from sauspiel_scraper.models import Game


def process_game_data(games: list[Game], me: str) -> pd.DataFrame:
    if not games:
        return pd.DataFrame()
    rows = []
    for g in games:
        val = 0
        try:
            val = int(re.sub(r"[^\d-]", "", g.meta.wert)) if g.meta.wert else 0
        except Exception:
            pass

        outcome = (g.meta.spielausgang or "").lower()
        won = "gewonnen" in outcome

        # Enhanced role logic: check 'roles' dict, fallback to title
        if g.roles and me in g.roles:
            role = g.roles[me]
        else:
            # Fallback for old data in DB
            title = g.title or ""
            role = "Spieler" if f"von {me}" in title else "Gegenspieler"

        # Identify the declarer from the title "GameType von Username"
        declarer = "Unknown"
        if g.title and " von " in g.title:
            declarer = g.title.split(" von ")[-1].strip()

        laufende = 0
        try:
            laufende = int(re.sub(r"[^\d]", "", g.meta.laufende)) if g.meta.laufende else 0
        except Exception:
            pass

        rows.append(
            {
                "game_id": g.game_id,
                "date": pd.to_datetime(g.meta.date),
                "type": g.game_type or "Unknown",
                "declarer": declarer,
                "won": won,
                "value": val if won else -val,
                "role": role,
                "laufende": laufende,
                "location": g.meta.location or "Unknown",
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date")
        df["cumulative_profit"] = df["value"].cumsum()
    return df
