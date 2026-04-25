import pandas as pd
import plotly.express as px
import streamlit as st

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
        is_me_declarer_side = role in ["Spieler", "Partner"]

        if is_me_declarer_side:
            is_my_win = is_declarer_win
            net_profit_cents = g.meta.value_int if is_declarer_win else -g.meta.value_int
        else:
            is_my_win = not is_declarer_win
            net_profit_cents = -g.meta.value_int if is_declarer_win else g.meta.value_int

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


def render_analytics(df: pd.DataFrame) -> None:
    st.header("📈 Analytics")

    with st.expander("🔍 Filter & Settings", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            date_range = st.date_input(
                "Date Range", value=(df["date"].min().date(), df["date"].max().date())
            )
        with c2:
            role_options = sorted(df["role"].unique().tolist())
            roles = st.multiselect("Roles", options=role_options, default=role_options)
        with c3:
            type_options = sorted(df["type"].unique().tolist())
            types = st.multiselect("Game Types", options=type_options, default=type_options)

    # Apply filters
    mask = (df["role"].isin(roles)) & (df["type"].isin(types))
    dr_list = list(date_range) if isinstance(date_range, (list, tuple)) else []
    if len(dr_list) == 2:
        mask &= (df["date"].dt.date >= dr_list[0]) & (df["date"].dt.date <= dr_list[1])

    f_df = df[mask].copy()
    if f_df.empty:
        st.warning("No data matches selected filters.")
        return

    f_df["cumulative_profit"] = f_df["value"].cumsum()

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Games", len(f_df))
    m2.metric("Win Rate", f"{(f_df['won'].mean() * 100):.1f}%")
    m3.metric("Profit/Loss", f"P {f_df['value'].sum():+d}")

    st.divider()
    st.plotly_chart(
        px.line(f_df, x="date", y="cumulative_profit", title="Profit Curve"), key="p_plot"
    )

    ca, cb = st.columns(2)
    with ca:
        st.plotly_chart(px.pie(f_df, names="type", title="Game Types", hole=0.4), key="t_plot")
    with cb:
        st.plotly_chart(
            px.pie(f_df, names="role", title="Role Distribution", hole=0.4), key="r_pie"
        )

    r_stats = f_df.groupby("role")["won"].mean().reset_index()
    r_stats["won"] *= 100
    st.plotly_chart(
        px.bar(r_stats, x="role", y="won", color="role", title="Win Rate by Role (%)"),
        key="r_plot",
    )

    st.divider()
    st.subheader("📋 Game List (Filtered)")
    # Show columns that are useful for sanity check
    display_df = f_df[
        ["game_id", "date", "type", "declarer", "role", "won", "value", "laufende", "location"]
    ].copy()
    display_df = display_df.sort_values("date", ascending=False)
    # Rename declarer to Spieler for the UI
    display_df = display_df.rename(columns={"declarer": "Spieler"})
    st.dataframe(display_df, width="stretch", hide_index=True)
