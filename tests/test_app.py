import pytest
import pandas as pd
from sauspiel_scraper.app import process_game_data

def test_process_game_data_with_dash_laufende():
    mock_games = [
        {
            "game_id": "12345",
            "game_type": "Sauspiel",
            "title": "Sauspiel von player1",
            "roles": {"player1": "Spieler"},
            "meta": {
                "date": "2024-03-20T12:00:00",
                "wert": "20",
                "spielausgang": "gewonnen",
                "laufende": "–",  # This is the problematic character
                "location": "Stammtisch"
            }
        }
    ]
    
    # This should not raise ValueError
    df = process_game_data(mock_games, "player1")
    
    assert not df.empty
    assert df.iloc[0]["laufende"] == 0

def test_process_game_data_with_none_title():
    mock_games = [
        {
            "game_id": "12346",
            "game_type": "Sauspiel",
            "title": None, # This should not raise TypeError
            "roles": None, # Also test for None roles
            "meta": {
                "date": "2024-03-20T12:00:00",
                "wert": "20",
                "spielausgang": "gewonnen",
                "laufende": "0",
                "location": "Stammtisch"
            }
        }
    ]
    
    # This should not raise TypeError
    df = process_game_data(mock_games, "player1")
    
    assert not df.empty
    assert df.iloc[0]["role"] == "Gegenspieler"
