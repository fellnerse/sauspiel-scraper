import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from sauspiel_scraper.main import app
from sauspiel_scraper.models import Game, GameMeta

runner = CliRunner()

@patch('sauspiel_scraper.main.Database')
def test_export_command(mock_db_class, tmp_path):
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db
    
    game = Game(
        game_id="123",
        meta=GameMeta(date=datetime(2024, 1, 1, 12, 0))
    )
    mock_db.get_all_games.return_value = [game]
    
    out_file = tmp_path / "export.jsonl"
    result = runner.invoke(app, ["export", "--username", "testuser", "--output", str(out_file)])
    
    assert result.exit_code == 0
    assert out_file.exists()
    
    content = out_file.read_text()
    assert "123" in content
    parsed = json.loads(content.splitlines()[0])
    assert parsed["game_id"] == "123"

@patch('sauspiel_scraper.main.Database')
def test_export_command_empty(mock_db_class, tmp_path):
    mock_db = MagicMock()
    mock_db_class.return_value = mock_db
    mock_db.get_all_games.return_value = []
    
    out_file = tmp_path / "export_empty.jsonl"
    result = runner.invoke(app, ["export", "--username", "testuser", "--output", str(out_file)])
    
    assert result.exit_code == 0
    assert not out_file.exists()
