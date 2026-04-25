from datetime import datetime

from sauspiel_scraper.app.analytics import process_game_data
from sauspiel_scraper.models import Game, GameMeta


def test_process_game_data_with_dash_laufende():
    mock_games = [
        Game(
            game_id="12345",
            game_type="Sauspiel",
            title="Sauspiel von player1",
            roles={"player1": "Spieler"},
            meta=GameMeta(
                date=datetime(2024, 3, 20, 12, 0),
                wert="20",
                spielausgang="gewonnen",
                laufende="–",
                location="Stammtisch",
            ),
        )
    ]

    # This should not raise ValueError
    df = process_game_data(mock_games, "player1")

    assert not df.empty
    assert df.iloc[0]["laufende"] == 0


def test_process_game_data_with_none_title():
    mock_games = [
        Game(
            game_id="12346",
            game_type="Sauspiel",
            title=None,
            roles={},
            meta=GameMeta(
                date=datetime(2024, 3, 20, 12, 0),
                wert="20",
                spielausgang="gewonnen",
                laufende="0",
                location="Stammtisch",
            ),
        )
    ]

    # This should not raise TypeError
    df = process_game_data(mock_games, "player1")

    assert not df.empty
    assert df.iloc[0]["role"] == "Gegenspieler"


def test_process_game_data_profit_calculation():
    mock_games = [
        Game(
            game_id="1",
            game_type="Sauspiel",
            title="Sauspiel von player1",
            roles={"player1": "Spieler", "player2": "Gegenspieler"},
            meta=GameMeta(
                date=datetime(2024, 3, 20, 12, 0),
                wert="20",
                spielausgang="gewonnen",
            ),
        ),
        Game(
            game_id="2",
            game_type="Sauspiel",
            title="Sauspiel von player2",
            roles={"player1": "Gegenspieler", "player2": "Spieler"},
            meta=GameMeta(
                date=datetime(2024, 3, 20, 12, 5),
                wert="30",
                spielausgang="verloren",
            ),
        ),
    ]

    df = process_game_data(mock_games, "player1")

    assert len(df) == 2
    # First game: won 20
    assert df.iloc[0]["value"] == 20
    # Second game: lost 30
    assert df.iloc[1]["value"] == -30
    # Cumulative profit: 20 + (-30) = -10
    assert df.iloc[1]["cumulative_profit"] == -10
