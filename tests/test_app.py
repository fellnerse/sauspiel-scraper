import pytest
import pandas as pd
from datetime import datetime
from sauspiel_scraper.app import process_game_data
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
                location="Stammtisch"
            )
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
                location="Stammtisch"
            )
        )
    ]
    
    # This should not raise TypeError
    df = process_game_data(mock_games, "player1")
    
    assert not df.empty
    assert df.iloc[0]["role"] == "Gegenspieler"
