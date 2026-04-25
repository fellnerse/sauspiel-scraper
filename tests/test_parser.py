from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from sauspiel_scraper.core import SauspielScraper
from sauspiel_scraper.models import GamePreview

FIXTURE_DIR = Path(__file__).parent / "fixtures"

def test_parse_overview_page():
    scraper = SauspielScraper()
    scraper.session = MagicMock()
    html = (FIXTURE_DIR / "overview.html").read_text()
    
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.status_code = 200
    scraper.session.get.return_value = mock_resp
    
    # We don't want it to keep going to page 2 in this test
    # so we mock it to return empty for subsequent calls
    mock_empty = MagicMock(text="<html></html>")
    scraper.session.get.side_effect = [mock_resp, mock_empty]
    
    games = scraper.get_game_list_paginated(max_new=20)
    
    assert len(games) > 0
    # Check first game in the fixture
    first_game = games[0]
    assert isinstance(first_game, GamePreview)
    assert first_game.game_id == "1558055578"
    assert first_game.date is not None
    assert first_game.deck_type == "Kurze Karte"

def test_parse_detail_page():
    scraper = SauspielScraper()
    scraper.session = MagicMock()
    html = (FIXTURE_DIR / "detail.html").read_text()
    
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.status_code = 200
    scraper.session.get.return_value = mock_resp
    
    # Using real meta info from overview fixture
    preview = GamePreview(
        game_id="1558055578",
        date=datetime(2026, 4, 15, 20, 8),
        deck_type="Kurze Karte"
    )
    
    game = scraper.scrape_game("1558055578", preview)
    
    assert game.game_id == "1558055578"
    assert len(game.players) == 4
    
    # Check roles
    assert len(game.roles) == 4
    for p in game.players:
        assert p in game.roles
        
    # Check initial hands
    assert len(game.initial_hands) == 4
    for p in game.players:
        assert len(game.initial_hands[p]) == 6 # Kurze Karte
        
    # Check tricks
    assert len(game.tricks) == 6
    for trick in game.tricks:
        assert trick.winner is not None
        assert len(trick.cards) == 4
