import json
from datetime import datetime

import streamlit as st

from sauspiel_scraper.core import SauspielScraper

if "games" not in st.session_state:
    st.session_state["games"] = []

def main() -> None:
    st.title("🎴 Sauspiel Scraper")
    st.markdown("Download your game history from sauspiel.de for analysis.")

    with st.sidebar:
        st.header("Login Settings")
        username = st.text_input("Username", value=st.secrets.get("USERNAME", ""))
        password = st.text_input("Password", type="password", value=st.secrets.get("PASSWORD", ""))
        
        st.divider()
        st.header("Scrape Settings")
        mode = st.radio("Mode", ["Last X Games", "Since Date"])
        
        count = None
        since_dt = None
        
        if mode == "Last X Games":
            count = st.number_input("Number of games", min_value=1, max_value=500, value=10)
        else:
            since = st.date_input("Since Date", value=datetime.now())
            since_dt = datetime.combine(since, datetime.min.time())

    if st.button("🚀 Start Scraping", type="primary"):
        if not username or not password:
            st.error("Please provide both username and password.")
            return

        scraper = SauspielScraper(username, password)
        
        with st.status("Logging in...") as status:
            if scraper.login():
                status.update(label="Logged in successfully!", state="running")
            else:
                status.update(label="Login failed!", state="error")
                st.error("Please check your credentials.")
                return

            status.update(label="Fetching game list...", state="running")
            game_list = scraper.get_game_list(limit=count, since=since_dt)
            total = len(game_list)
            
            if total == 0:
                status.update(label="No games found.", state="complete")
                st.warning("No games found for your user ID.")
                return
                
            status.update(label=f"Found {total} games. Starting scrape...", state="running")
            
            progress_bar = st.progress(0)
            progress_text = st.empty()
            
            results = []
            for i, game_info in enumerate(game_list):
                progress_text.text(f"Scraping Game {game_info['game_id']} ({i+1}/{total})")
                try:
                    game_data = scraper.scrape_game(game_info["game_id"], game_info)
                    results.append(game_data)
                except Exception as e:
                    st.error(f"Error scraping game {game_info['game_id']}: {e}")
                
                progress_bar.progress((i + 1) / total)
            
            status.update(label=f"Scraped {len(results)} games successfully!", state="complete")
            st.session_state["games"] = results

    if st.session_state["games"]:
        st.divider()
        st.subheader(f"Results ({len(st.session_state['games'])} games)")
        
        # Display as JSONL format
        jsonl_text = "\n".join([json.dumps(g, ensure_ascii=False) for g in st.session_state["games"]])
        st.text_area("JSONL Output", value=jsonl_text, height=400)
        
        st.download_button(
            label="📥 Download JSONL",
            data=jsonl_text,
            file_name=f"sauspiel_games_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl",
            mime="application/jsonl"
        )
        
        with st.expander("Raw JSON (Pretty)"):
            st.json(st.session_state["games"])

def run_app() -> None:
    import sys
    from streamlit.web import cli as stcli
    from pathlib import Path
    
    app_path = Path(__file__).resolve()
    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
