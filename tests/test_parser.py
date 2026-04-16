import pytest
from pathlib import Path
from unittest.mock import MagicMock
from sauspiel_scraper.core import SauspielScraper

FIXTURE_DIR = Path(__file__).parent / "fixtures"

def test_parse_overview_page():
    scraper = SauspielScraper()
    scraper.session = MagicMock()
    html = (FIXTURE_DIR / "overview.html").read_text()
    
    mock_resp = MagicMock()
    mock_resp.text = html
    scraper.session.get.return_value = mock_resp
    
    # We don't want it to keep going to page 2 in this test
    # so we mock it to return empty for subsequent calls
    mock_empty = MagicMock(text="<html></html>")
    scraper.session.get.side_effect = [mock_resp, mock_empty]
    
    games = scraper.get_game_list_paginated(max_new=20)
    
    assert len(games) > 0
    # Check first game in the fixture
    first_game = games[0]
    assert "game_id" in first_game
    assert first_game["game_id"] == "1558055578"
    assert "date" in first_game
    assert "deck_type" in first_game
    assert first_game["deck_type"] == "Kurze Karte"

def test_parse_detail_page():
    scraper = SauspielScraper()
    scraper.session = MagicMock()
    html = (FIXTURE_DIR / "detail.html").read_text()
    
    mock_resp = MagicMock()
    mock_resp.text = html
    scraper.session.get.return_value = mock_resp
    
    # Using real meta info from overview fixture
    meta = {
        "game_id": "1558055578",
        "date": "2026-04-15T20:08:00",
        "deck_type": "Kurze Karte"
    }
    
    game_data = scraper.scrape_game("1558055578", meta)
    
    assert game_data["game_id"] == "1558055578"
    assert len(game_data["players"]) == 4
    
    # Check roles
    # Note: These names are from the actual crawled HTML
    players = game_data["players"]
    assert len(game_data["roles"]) == 4
    for p in players:
        assert p in game_data["roles"]
        
    # Check initial hands
    assert len(game_data["initial_hands"]) == 4
    for p in players:
        assert len(game_data["initial_hands"][p]) == 6 # Kurze Karte
        
    # Check tricks
    assert len(game_data["tricks"]) == 6
    for trick in game_data["tricks"]:
        assert "winner" in trick
        assert "cards" in trick
        assert len(trick["cards"]) == 4
