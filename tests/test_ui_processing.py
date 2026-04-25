from datetime import datetime

from sauspiel_scraper.app.analytics import games_to_df, process_game_data
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

    processed = process_game_data(mock_games, "player1")

    assert len(processed) == 1
    assert processed[0].laufende == 0


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

    processed = process_game_data(mock_games, "player1")

    assert len(processed) == 1
    assert processed[0].role == "Gegenspieler"


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

    processed = process_game_data(mock_games, "player1")

    assert len(processed) == 2
    # First game: player1 is declarer, won 20
    assert processed[0].role == "Spieler"
    assert processed[0].is_my_win is True
    assert processed[0].net_profit_cents == 20

    # Second game: player1 is opponent, declarer (player2) lost 30
    # Thus player1 won 30!
    assert processed[1].role == "Gegenspieler"
    assert processed[1].is_my_win is True
    assert processed[1].net_profit_cents == 30

    # Test conversion to DataFrame
    df = games_to_df(processed)
    assert len(df) == 2
    assert df.iloc[0]["value"] == 20
    assert df.iloc[1]["value"] == 30


def test_process_game_data_opponent_lost():
    mock_games = [
        Game(
            game_id="3",
            game_type="Sauspiel",
            title="Sauspiel von player2",
            roles={"player1": "Gegenspieler", "player2": "Spieler"},
            meta=GameMeta(
                date=datetime(2024, 3, 20, 12, 10),
                wert="50",
                spielausgang="gewonnen",
            ),
        )
    ]
    processed = process_game_data(mock_games, "player1")
    assert processed[0].role == "Gegenspieler"
    assert processed[0].is_declarer_win is True
    assert processed[0].is_my_win is False
    assert processed[0].net_profit_cents == -50


def test_process_game_data_mitspieler_role():
    # 'Mitspieler' should be recognized as declarer side
    mock_games = [
        Game(
            game_id="5",
            game_type="Sauspiel",
            title="Sauspiel von player2",
            roles={"player1": "Mitspieler", "player2": "Spieler"},
            meta=GameMeta(
                date=datetime(2024, 3, 20, 12, 20),
                wert="80",  # Total value
                spielausgang="gewonnen",
            ),
        )
    ]
    processed = process_game_data(mock_games, "player1")
    assert processed[0].role == "Mitspieler"
    assert processed[0].is_my_win is True
    assert processed[0].net_profit_cents == 80


def test_process_game_data_solo_opponent():
    mock_games = [
        Game(
            game_id="6",
            game_type="Eichel-Solo",
            title="Eichel-Solo von player2",
            roles={"player1": "Gegenspieler", "player2": "Spieler"},
            meta=GameMeta(
                date=datetime(2024, 3, 20, 12, 25),
                wert="300",
                spielausgang="gewonnen",
            ),
        )
    ]
    processed = process_game_data(mock_games, "player1")
    assert processed[0].role == "Gegenspieler"
    assert processed[0].is_my_win is False
    # Should be -100 (300 / 3)
    assert processed[0].net_profit_cents == -100


def test_process_game_data_solo_declarer():
    mock_games = [
        Game(
            game_id="7",
            game_type="Wenz",
            title="Wenz von player1",
            roles={"player1": "Spieler", "player2": "Gegenspieler"},
            meta=GameMeta(
                date=datetime(2024, 3, 20, 12, 30),
                wert="420",
                spielausgang="verloren",
            ),
        )
    ]
    processed = process_game_data(mock_games, "player1")
    assert processed[0].role == "Spieler"
    assert processed[0].is_my_win is False
    # Should be -420 (Total loss for declarer)
    assert processed[0].net_profit_cents == -420
