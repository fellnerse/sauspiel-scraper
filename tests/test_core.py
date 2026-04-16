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
    assert params["player_id"] == "123"  # Verify we re-added it
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
    
    # Page 1 has 20 games (triggers next page)
    items_p1 = "".join([f'<div class="games-item"><h4 class="card-title"><a href="/spiele/{i}"></a></h4></div>' for i in range(20)])
    html1 = f"<div>{items_p1}</div>"
    
    # Page 2 has 1 game (stops pagination)
    html2 = '<div class="games-item"><h4 class="card-title"><a href="/spiele/102"></a></h4></div>'
    
    mock_resp1 = MagicMock(text=html1)
    mock_resp2 = MagicMock(text=html2)
    
    scraper.session.get.side_effect = [mock_resp1, mock_resp2]
    
    db = MagicMock(spec=Database)
    db.game_exists.return_value = False 
    
    new_games = scraper.get_game_list_paginated(max_new=50, db=db)
    
    assert len(new_games) == 21
    assert scraper.session.get.call_count == 2

def test_identify_user_id():
    scraper = SauspielScraper(username="testuser")
    html = '<a data-userid="456" data-username="testuser" href="/profile/456-testuser">Profile</a>'
    scraper._identify_user_id(html)
    assert scraper.user_id == "456"

def test_get_game_list_paginated_no_userid_needed():
    scraper = SauspielScraper()
    scraper.user_id = None # Simulate not yet identified
    scraper.session = MagicMock()
    mock_resp = MagicMock(text='<div class="games-item"><h4 class="card-title"><a href="/spiele/123"></a></h4></div>')
    scraper.session.get.return_value = mock_resp
    
    new_games = scraper.get_game_list_paginated(max_new=1)
    assert len(new_games) == 1
    assert new_games[0]["game_id"] == "123"
