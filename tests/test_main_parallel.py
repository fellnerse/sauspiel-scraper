from datetime import datetime
from unittest.mock import MagicMock, patch

from sauspiel_scraper.models import GamePreview


@patch("sauspiel_scraper.main.Database")
@patch("sauspiel_scraper.main.SauspielScraper")
@patch("sauspiel_scraper.main.Progress")
def test_scrape_parallel_orchestration(mock_progress, mock_scraper_cls, mock_db_cls):
    # Setup mocks
    mock_scraper = mock_scraper_cls.return_value
    mock_scraper.login.return_value = True

    mock_preview = GamePreview(game_id="123", date=datetime.now())
    mock_scraper.get_game_list_paginated.return_value = [mock_preview]

    mock_scraper.scrape_game.return_value = MagicMock()
    mock_scraper.rate_limiter.total_requests = 1
    mock_scraper.rate_limiter.total_429s = 0

    # Call scrape (with minimal count to keep it fast)
    from typer.testing import CliRunner

    from sauspiel_scraper.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["scrape", "-u", "user", "-p", "pass", "-c", "1"])

    assert result.exit_code == 0
    mock_scraper.scrape_game.assert_called()
    assert "Done! Scraped 1 games" in result.output
    assert "Total Requests: 1" in result.output
