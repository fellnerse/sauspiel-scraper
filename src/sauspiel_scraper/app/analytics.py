import pandas as pd
import plotly.express as px
import plotly.io as pio

from sauspiel_scraper.models import Game, ProcessedGame


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

        is_declarer_win = g.meta.is_won
        is_me_declarer_side = role in ["Spieler", "Mitspieler", "Partner"]

        # Base profit calculation logic:
        # 1. Sauspiel (Partner game): 2 winners get wert/2 each, 2 losers pay wert/2 each.
        # 2. Solo/Wenz/Geier (1 vs 3):
        #    - Declarer gets wert (3 * individual) or pays wert (3 * individual).
        #    - Each opponent pays wert/3 or gets wert/3.

        value = g.meta.value_int
        game_type = (g.game_type or "").lower()
        is_solo = any(s in game_type for s in ["solo", "wenz", "geier", "bettel"])

        if is_me_declarer_side:
            is_my_win = is_declarer_win
            # Declarer (and partner in Sauspiel) gets/pays the value shown in 'wert'
            net_profit_cents = value if is_my_win else -value
        else:
            is_my_win = not is_declarer_win
            if is_solo:
                # In Solo, the 'wert' is the total declarer value, so each opponent gets 1/3
                net_profit_cents = (-value if is_declarer_win else value) // 3
            else:
                # In Sauspiel, each opponent pays/gets the full value shown in 'wert'
                net_profit_cents = -value if is_declarer_win else value
        processed.append(
            ProcessedGame(
                game_id=g.game_id,
                date=g.meta.date,
                game_type=g.game_type or "Unknown",
                declarer=declarer,
                role=role,
                is_declarer_win=is_declarer_win,
                is_my_win=is_my_win,
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
            "is_my_win": "won",
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
    # Map boolean to strings for better legend
    df["Result"] = df["won"].map({True: "Win", False: "Loss"})
    fig_winloss = px.pie(
        df,
        names="Result",
        title="Win/Loss Distribution",
        color="Result",
        color_discrete_map={"Win": "#4caf50", "Loss": "#f44336"},
        template="plotly_white",
    )

    # Use a faster JSON-based approach if possible, but the prompt suggested to_html
    return {
        "profit_chart": pio.to_html(fig_profit, full_html=False, include_plotlyjs="cdn"),
        "types_chart": pio.to_html(fig_types, full_html=False, include_plotlyjs="cdn"),
        "winloss_chart": pio.to_html(fig_winloss, full_html=False, include_plotlyjs="cdn"),
    }
