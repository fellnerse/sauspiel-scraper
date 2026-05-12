import pandas as pd
import plotly.express as px
import plotly.io as pio

from sauspiel_scraper.models import Game, GameResult, ProcessedGame


def process_game_data(games: list[Game], me: str) -> list[ProcessedGame]:
    if not games:
        return []

    processed = []
    for g in games:
        # Identify the declarer from the title "GameType von Username"
        declarer = "Unknown"
        if g.title and " von " in g.title:
            # Use split once from the left to handle names with spaces if needed
            # although Sauspiel names usually don't have spaces, " von " is the reliable separator
            parts = g.title.split(" von ", 1)
            if len(parts) > 1:
                declarer = parts[1].strip()

        # Identify role
        if g.roles and me in g.roles:
            role = g.roles[me]
        else:
            role = "Spieler" if declarer == me else "Gegenspieler"

        game_type_raw = (g.game_type or "").lower()
        is_zamgworfen = "zamgworfen" in game_type_raw
        is_solo = any(s in game_type_raw for s in ["solo", "wenz", "geier", "bettel"])

        if is_zamgworfen:
            declarer_result = GameResult.DRAW
            my_result = GameResult.DRAW
            net_profit_cents = 0
        else:
            is_declarer_win = g.meta.is_won
            is_me_declarer_side = role in ["Spieler", "Mitspieler", "Partner"]

            value = g.meta.value_int

            if is_me_declarer_side:
                my_win_bool = is_declarer_win
                net_profit_cents = value if my_win_bool else -value
            else:
                my_win_bool = not is_declarer_win
                if is_solo:
                    net_profit_cents = (-value if is_declarer_win else value) // 3
                else:
                    net_profit_cents = -value if is_declarer_win else value

            declarer_result = GameResult.WIN if is_declarer_win else GameResult.LOSS
            my_result = GameResult.WIN if my_win_bool else GameResult.LOSS

        processed.append(
            ProcessedGame(
                game_id=g.game_id,
                date=g.meta.date,
                game_type=g.game_type or "Unknown",
                declarer=declarer,
                role=role,
                declarer_result=declarer_result,
                my_result=my_result,
                net_profit_cents=net_profit_cents,
                laufende=g.meta.laufende_int,
                location=g.meta.location or "Unknown",
            )
        )
    return processed


def games_to_df(games: list[ProcessedGame]) -> pd.DataFrame:
    if not games:
        return pd.DataFrame()

    data = [g.model_dump() for g in games]
    df = pd.DataFrame(data)

    # Rename fields for compatibility with existing UI code
    df = df.rename(
        columns={
            "game_type": "type",
            "my_result": "won",
            "net_profit_cents": "value",
        }
    )

    if not df.empty:
        df = df.sort_values("date")
    return df


def render_analytics(games: list[ProcessedGame]) -> dict[str, str]:
    if not games:
        return {}

    df = games_to_df(games)
    if df.empty:
        return {}

    # Ensure date is datetime for plotting
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # Cumulative Profit
    df["cumulative_profit"] = df["value"].cumsum() / 100.0

    fig_profit = px.line(
        df,
        x="date",
        y="cumulative_profit",
        title="Cumulative Profit (€)",
        labels={"cumulative_profit": "Profit (€)", "date": "Date"},
        template="plotly_white",
    )

    # Game Type Distribution
    fig_types = px.pie(
        df,
        names="type",
        title="Game Type Distribution",
        template="plotly_white",
    )

    # Win/Loss Distribution
    # Map enum to strings for better legend
    df["Result"] = df["won"].map(
        {GameResult.WIN: "Win", GameResult.LOSS: "Loss", GameResult.DRAW: "Draw"}
    )
    fig_winloss = px.pie(
        df,
        names="Result",
        title="Win/Loss Distribution",
        color="Result",
        color_discrete_map={"Win": "#4caf50", "Loss": "#f44336", "Draw": "#9e9e9e"},
        template="plotly_white",
    )

    # Use a faster JSON-based approach if possible, but the prompt suggested to_html
    return {
        "profit_chart": pio.to_html(fig_profit, full_html=False, include_plotlyjs="cdn"),
        "types_chart": pio.to_html(fig_types, full_html=False, include_plotlyjs="cdn"),
        "winloss_chart": pio.to_html(fig_winloss, full_html=False, include_plotlyjs="cdn"),
    }
