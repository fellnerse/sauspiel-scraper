import pytest
from unittest.mock import MagicMock, patch
from sauspiel_scraper.core import SauspielScraper, Database

def test_get_game_list_paginated_params():
    scraper = SauspielScraper()
    scraper.user_id = "123"
    scraper.session = MagicMock()
    
    # Mock response with no games to stop the loop
    mock_resp = MagicMock()
    mock_resp.text = "<html><body></body></html>"
    scraper.session.get.return_value = mock_resp
    
    scraper.get_game_list_paginated(max_new=5)
    
    # Verify the first call's parameters
    # The URL should be the base URL + /spiele
    args, kwargs = scraper.session.get.call_args
    assert args[0].endswith("/spiele")
    
    params = kwargs.get("params", {})
    assert params["role"] == "all"
    assert "player_id" not in params  # Verify we removed it to ensure role=all works
    assert params["page"] == 1

def test_get_game_list_paginated_finds_new_games():
    scraper = SauspielScraper()
    scraper.user_id = "123"
    scraper.session = MagicMock()
    
    # Mock HTML with one game
    html = """
    <div class="games-item">
        <h4 class="card-title"><a href="/spiele/999999">Sauspiel</a></h4>
        <p class="card-title-subtext">20.03.2024 12:00 — Eichel</p>
    </div>
    """
    mock_resp_page1 = MagicMock()
    mock_resp_page1.text = html
    
    # Response for "next page" check - we'll just say no next page link
    mock_resp_empty = MagicMock()
    mock_resp_empty.text = "<html><body></body></html>"
    
    # We need to return the page1 then stop
    scraper.session.get.side_effect = [mock_resp_page1, mock_resp_empty]
    
    db = MagicMock(spec=Database)
    db.game_exists.return_value = False # Simulate new game
    
    new_games = scraper.get_game_list_paginated(max_new=5, db=db)
    
    assert len(new_games) == 1
    assert new_games[0]["game_id"] == "999999"
    db.game_exists.assert_called_with("999999")

def test_get_game_list_paginated_skips_existing():
    scraper = SauspielScraper()
    scraper.user_id = "123"
    scraper.session = MagicMock()
    
    html = """
    <div class="games-item">
        <h4 class="card-title"><a href="/spiele/888888">Sauspiel</a></h4>
        <p class="card-title-subtext">20.03.2024 12:00 — Eichel</p>
    </div>
    """
    mock_resp = MagicMock()
    mock_resp.text = html
    
    # Stop after one page
    scraper.session.get.side_effect = [mock_resp, MagicMock(text="")]
    
    db = MagicMock(spec=Database)
    db.game_exists.return_value = True # Simulate already exists
    
    new_games = scraper.get_game_list_paginated(max_new=5, db=db)
    
    assert len(new_games) == 0
    db.game_exists.assert_called_with("888888")

def test_get_game_list_paginated_multiple_pages():
    scraper = SauspielScraper()
    scraper.user_id = "123"
    scraper.session = MagicMock()
    
    # Page 1 has 1 game
    html1 = """
    <div class="games-item">
        <h4 class="card-title"><a href="/spiele/101">Sauspiel</a></h4>
        <p class="card-title-subtext">20.03.2024 12:00 — Eichel</p>
    </div>
    <a class="next_page" href="/spiele?page=2">Next</a>
    """
    # Page 2 has 1 game
    html2 = """
    <div class="games-item">
        <h4 class="card-title"><a href="/spiele/102">Sauspiel</a></h4>
        <p class="card-title-subtext">19.03.2024 12:00 — Eichel</p>
    </div>
    """
    
    mock_resp1 = MagicMock(text=html1)
    mock_resp2 = MagicMock(text=html2)
    mock_resp3 = MagicMock(text="<html><body></body></html>")
    
    scraper.session.get.side_effect = [mock_resp1, mock_resp2, mock_resp3]
    
    db = MagicMock(spec=Database)
    db.game_exists.return_value = False # All are new
    
    # Requesting 50 games should trigger multiple pages
    new_games = scraper.get_game_list_paginated(max_new=50, db=db)
    
    assert len(new_games) == 2
    assert new_games[0]["game_id"] == "101"
    assert new_games[1]["game_id"] == "102"
    assert scraper.session.get.call_count == 2 # Should only call 2 pages because Page 2 has no next_page link
