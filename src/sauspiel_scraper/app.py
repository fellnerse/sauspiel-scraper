import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from sauspiel_scraper.core import Database, SauspielScraper

SESSION_FILE = Path("output/session.json")

def save_session(scraper: SauspielScraper) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(scraper.get_session_data(), f)

def load_stored_session() -> SauspielScraper | None:
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
            scraper = SauspielScraper()
            scraper.load_session_data(data)
            if scraper.is_logged_in():
                return scraper
        except Exception:
            pass
    return None

def process_game_data(games: list[dict[str, Any]], me: str) -> pd.DataFrame:
    if not games:
        return pd.DataFrame()
    
    rows = []
    for g in games:
        meta = g.get("meta", {})
        raw_val = meta.get("wert", "0")
        val = 0
        try:
            val = int(re.sub(r"[^\d-]", "", raw_val))
        except Exception:
            pass
            
        outcome = meta.get("spielausgang", "").lower()
        won = "gewonnen" in outcome
        
        if f"von {me}" in g.get("title", ""):
            role = "Spieler"
        else:
            role = "Gegenspieler"

        rows.append({
            "game_id": g.get("game_id"),
            "date": pd.to_datetime(meta.get("date")),
            "type": g.get("game_type", "Unknown"),
            "won": won,
            "value": val if won else -val,
            "role": role,
            "laufende": int(meta.get("laufende", "0")),
            "location": meta.get("location", "Unknown"),
        })
        
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date")
        df["cumulative_profit"] = df["value"].cumsum()
    return df

def render_analytics(df: pd.DataFrame) -> None:
    st.header("📈 Analytics")
    
    with st.expander("🔍 Filters", expanded=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            date_range = st.date_input("Date Range", value=(df["date"].min().date(), df["date"].max().date()))
        with col_f2:
            roles = st.multiselect("Roles", options=df["role"].unique(), default=list(df["role"].unique()))
        with col_f3:
            types = st.multiselect("Game Types", options=df["type"].unique(), default=list(df["type"].unique()))

    # Apply filters
    mask = (df["role"].isin(roles)) & (df["type"].isin(types))
    # ty has issues with dynamic tuple lengths from streamlit, so we use a list conversion
    dr_list = list(date_range) if isinstance(date_range, (list, tuple)) else []
    if len(dr_list) == 2:
        mask &= (df["date"].dt.date >= dr_list[0]) & (df["date"].dt.date <= dr_list[1])
    
    filtered_df = df[mask].copy()

    if filtered_df.empty:
        st.warning("No data matches the selected filters.")
        return

    filtered_df["cumulative_profit"] = filtered_df["value"].cumsum()

    m_winrate = (filtered_df["won"].mean() * 100)
    m_profit = filtered_df["value"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Games", len(filtered_df))
    c2.metric("Win Rate", f"{m_winrate:.1f}%")
    c3.metric("Profit/Loss", f"P {m_profit:+d}")

    st.divider()

    fig_profit = px.line(filtered_df, x="date", y="cumulative_profit", title="Cumulative Profit")
    st.plotly_chart(fig_profit, key="profit_chart")

    ca, cb = st.columns(2)
    with ca:
        fig_types = px.pie(filtered_df, names="type", title="Game Distribution", hole=0.4)
        st.plotly_chart(fig_types, key="types_chart")
    with cb:
        role_stats = filtered_df.groupby("role")["won"].mean().reset_index()
        role_stats["won"] *= 100
        fig_role = px.bar(role_stats, x="role", y="won", color="role", title="Win Rate by Role (%)")
        st.plotly_chart(fig_role, key="role_chart")

def main() -> None:
    st.set_page_config(page_title="Sauspiel Scraper", page_icon="🎴", layout="wide")
    
    if "scraper" not in st.session_state:
        st.session_state["scraper"] = load_stored_session()
    if "db" not in st.session_state:
        st.session_state["db"] = Database()

    st.title("🎴 Sauspiel Scraper & Analytics")

    with st.sidebar:
        if st.session_state["scraper"] is None:
            st.header("🔑 Login")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Login", type="primary"):
                    scraper = SauspielScraper(username, password)
                    with st.spinner("Logging in..."):
                        if scraper.login():
                            st.session_state["scraper"] = scraper
                            save_session(scraper)
                            st.rerun()
                        else:
                            st.error("Login failed.")
        else:
            st.success(f"Logged in: **{st.session_state['scraper'].username}**")
            if st.button("Logout"):
                st.session_state["scraper"] = None
                if SESSION_FILE.exists(): SESSION_FILE.unlink()
                st.rerun()

    if st.session_state["scraper"] is None:
        st.info("Please login to start.")
        return

    scraper = st.session_state["scraper"]
    db = st.session_state["db"]

    st.header("⚙️ Scrape New Games")
    col1, col2 = st.columns([1, 1])
    with col1:
        mode = st.radio("Mode", ["Last X Games", "Since Date"], horizontal=True)
    with col2:
        if mode == "Last X Games":
            count = st.number_input("Limit", min_value=1, max_value=1000, value=20)
            since_dt = None
        else:
            since = st.date_input("Since", value=datetime.now())
            since_dt = datetime.combine(since, datetime.min.time())
            count = None

    if st.button("🚀 Run Scraper", type="primary"):
        with st.status("Fetching game list...") as status:
            game_list = scraper.get_game_list(limit=count, since=since_dt)
            new_games = [g for g in game_list if not db.game_exists(g["game_id"])]
            
            if not new_games:
                status.update(label="All games already in database!", state="complete")
            else:
                status.update(label=f"Found {len(new_games)} new games. Scraping...", state="running")
                pbar = st.progress(0)
                ptext = st.empty()
                for i, info in enumerate(new_games):
                    gid = info["game_id"]
                    ptext.markdown(f"Scraping `{gid}` ({i+1}/{len(new_games)})")
                    try:
                        data = scraper.scrape_game(gid, info)
                        db.save_game(gid, info.get("date", ""), data.get("game_type", ""), data)
                    except Exception as e:
                        st.error(f"Error {gid}: {e}")
                    pbar.progress((i+1)/len(new_games))
                status.update(label=f"Done! Added {len(new_games)} games.", state="complete")
                st.balloons()

    all_games = db.get_all_games()
    if all_games:
        df = process_game_data(all_games, scraper.username)
        st.divider()
        render_analytics(df)
    else:
        st.info("Database is empty. Run the scraper first.")

def run_app() -> None:
    import sys
    from streamlit.web import cli as stcli
    app_path = Path(__file__).resolve()
    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
