import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from sauspiel_scraper.core import SauspielScraper

SESSION_FILE = Path("output/session.json")

# Initialize session state
if "games" not in st.session_state:
    st.session_state["games"] = []
if "scraper" not in st.session_state:
    st.session_state["scraper"] = None

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

def process_game_data(games: list[dict[str, Any]]) -> pd.DataFrame:
    if not games:
        return pd.DataFrame()
    
    rows = []
    for g in games:
        meta = g.get("meta", {})
        # Parse value: "P 240" -> 240
        raw_val = meta.get("wert", "0")
        val = 0
        try:
            val = int(re.sub(r"[^\d-]", "", raw_val))
        except:
            pass
            
        # Parse outcome
        outcome = meta.get("spielausgang", "").lower()
        won = "gewonnen" in outcome
        
        # Identify role (find yourself in players list)
        me = st.session_state["scraper"].username if st.session_state["scraper"] else "beschderPlayer"
        role = "Unknown"
        if me in g.get("players", []):
             # This is a bit tricky as Sauspiel usually lists the declarer. 
             # For now we use the title if it contains "von [me]"
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

def show_scraper_page() -> None:
    st.title("🎴 Sauspiel Scraper")
    
    if st.session_state["scraper"] is None:
        st.info("Please login via the sidebar to start scraping.")
        return

    scraper = st.session_state["scraper"]
    st.header("⚙️ Scraper Settings")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        mode = st.radio("Selection Mode", ["Last X Games", "Since Date"], horizontal=True)
    
    with col2:
        if mode == "Last X Games":
            count = st.number_input("How many games?", min_value=1, max_value=1000, value=10)
            since_dt = None
        else:
            since = st.date_input("Scrape games since:", value=datetime.now())
            since_dt = datetime.combine(since, datetime.min.time())
            count = None

    if st.button("🚀 Start Scraping", type="primary", use_container_width=True):
        st.session_state["games"] = []
        
        with st.status("Fetching game list...") as status:
            game_list = scraper.get_game_list(limit=count, since=since_dt)
            total = len(game_list)
            if total == 0:
                status.update(label="No games found.", state="complete")
                st.warning("No games found for your user ID.")
                return
            status.update(label=f"Found {total} games. Ready to scrape.", state="complete")

        st.divider()
        st.subheader("📊 Progress")
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        results = []
        for i, game_info in enumerate(game_list):
            gid = game_info['game_id']
            progress_text.markdown(f"**Scraping:** Game `{gid}` ({i+1} of {total})")
            
            try:
                game_data = scraper.scrape_game(gid, game_info)
                results.append(game_data)
            except Exception as e:
                st.error(f"Error scraping game {gid}: {e}")
            
            progress_bar.progress((i + 1) / total)
        
        progress_text.success(f"✅ Successfully scraped {len(results)} games!")
        st.session_state["games"] = results
        st.balloons()

    if st.session_state["games"]:
        st.divider()
        st.subheader(f"📦 Results ({len(st.session_state['games'])} games)")
        jsonl_text = "\n".join([json.dumps(g, ensure_ascii=False) for g in st.session_state["games"]])
        st.text_area("JSONL Preview", value=jsonl_text, height=200)
        
        col_dl, col_clr = st.columns(2)
        with col_dl:
            st.download_button(
                label="📥 Download JSONL",
                data=jsonl_text,
                file_name=f"sauspiel_games_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl",
                mime="application/jsonl",
                use_container_width=True
            )
        with col_clr:
            if st.button("🗑️ Clear Results", use_container_width=True):
                st.session_state["games"] = []
                st.rerun()

def show_analytics_page() -> None:
    st.title("📈 Game Analytics")
    
    # Allow loading from file or using current session
    uploaded_file = st.file_uploader("Upload your games.jsonl for analysis", type=["jsonl"])
    
    analysis_data = []
    if uploaded_file:
        for line in uploaded_file:
            analysis_data.append(json.loads(line))
    elif st.session_state["games"]:
        analysis_data = st.session_state["games"]
    else:
        st.info("No data found. Either scrape some games or upload a `.jsonl` file.")
        return

    df = process_game_data(analysis_data)
    if df.empty:
        st.warning("Could not process any valid game data.")
        return

    # --- TOP LEVEL METRICS ---
    m_winrate = (df["won"].mean() * 100)
    m_profit = df["value"].sum()
    m_count = len(df)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Games", f"{m_count}")
    col2.metric("Win Rate", f"{m_winrate:.1f}%")
    col3.metric("Net Profit/Loss", f"P {m_profit:+d}")

    st.divider()

    # --- CHARTS ---
    
    # 1. Profit Curve
    st.subheader("Career Path (Cumulative Profit)")
    fig_profit = px.line(df, x="date", y="cumulative_profit", 
                         title="Total Profit over Time",
                         labels={"cumulative_profit": "Profit (Points)", "date": "Date"})
    st.plotly_chart(fig_profit, use_container_width=True)

    col_a, col_b = st.columns(2)
    
    with col_a:
        # 2. Game Types Distribution
        st.subheader("Game Types")
        type_counts = df["type"].value_counts().reset_index()
        fig_types = px.pie(type_counts, names="type", values="count", hole=0.4)
        st.plotly_chart(fig_types, use_container_width=True)

    with col_b:
        # 3. Win Rate by Role
        st.subheader("Performance by Role")
        role_stats = df.groupby("role")["won"].mean().reset_index()
        role_stats["won"] *= 100
        fig_role = px.bar(role_stats, x="role", y="won", color="role", 
                          title="Win Rate %",
                          labels={"won": "Win Rate %"})
        st.plotly_chart(fig_role, use_container_width=True)

    # 4. Weekday Analysis
    st.subheader("Performance by Weekday")
    df["weekday"] = df["date"].dt.day_name()
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_stats = df.groupby("weekday")["won"].mean().reindex(weekday_order).reset_index()
    weekday_stats["won"] *= 100
    fig_weekday = px.bar(weekday_stats, x="weekday", y="won", title="Win Rate per Weekday")
    st.plotly_chart(fig_weekday, use_container_width=True)

    # --- TABLE ---
    with st.expander("Show raw data table"):
        st.dataframe(df)

import re

def main() -> None:
    st.set_page_config(page_title="Sauspiel Scraper", page_icon="🎴", layout="wide")
    
    # Try to auto-login
    if st.session_state["scraper"] is None:
        stored_scraper = load_stored_session()
        if stored_scraper:
            st.session_state["scraper"] = stored_scraper

    # --- Sidebar ---
    with st.sidebar:
        if st.session_state["scraper"] is None:
            st.header("🔑 Login")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                login_submit = st.form_submit_button("Login", type="primary", use_container_width=True)
                if login_submit:
                    scraper = SauspielScraper(username, password)
                    with st.spinner("Checking..."):
                        if scraper.login():
                            st.session_state["scraper"] = scraper
                            save_session(scraper)
                            st.rerun()
                        else:
                            st.error("Login failed.")
        else:
            st.success(f"Logged in as **{st.session_state['scraper'].username}**")
            if st.button("Logout", use_container_width=True):
                st.session_state["scraper"] = None
                if SESSION_FILE.exists(): SESSION_FILE.unlink()
                st.session_state["games"] = []
                st.rerun()

        st.divider()
        page = st.selectbox("Navigation", ["Scraper", "Analytics"])

    if page == "Scraper":
        show_scraper_page()
    else:
        show_analytics_page()

def run_app() -> None:
    import sys
    from streamlit.web import cli as stcli
    app_path = Path(__file__).resolve()
    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
