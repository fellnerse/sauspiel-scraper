import pandas as pd
import plotly.express as px
import streamlit as st

from sauspiel_scraper.models import Game


def process_game_data(games: list[Game], me: str) -> pd.DataFrame:
    if not games:
        return pd.DataFrame()
    rows = []
    for g in games:
        # Identify the declarer from the title "GameType von Username"
        declarer = "Unknown"
        if g.title and " von " in g.title:
            declarer = g.title.split(" von ")[-1].strip()

        # Identify role
        if g.roles and me in g.roles:
            role = g.roles[me]
        else:
            role = "Spieler" if f"von {me}" in (g.title or "") else "Gegenspieler"

        rows.append(
            {
                "game_id": g.game_id,
                "date": g.meta.date,
                "type": g.game_type or "Unknown",
                "declarer": declarer,
                "won": g.meta.is_won,
                "value": g.meta.value_int if g.meta.is_won else -g.meta.value_int,
                "role": role,
                "laufende": g.meta.laufende_int,
                "location": g.meta.location or "Unknown",
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date")
        df["cumulative_profit"] = df["value"].cumsum()
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
