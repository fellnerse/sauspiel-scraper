import json
from datetime import datetime

import streamlit as st

from sauspiel_scraper.core import SauspielScraper

if "games" not in st.session_state:
    st.session_state["games"] = []

def main() -> None:
    st.set_page_config(page_title="Sauspiel Scraper", page_icon="🎴")
    st.title("🎴 Sauspiel Scraper")
    st.markdown("Archive your Sauspiel game history for analysis.")

    with st.sidebar:
        with st.form("scrape_settings"):
            st.header("Login Settings")
            username = st.text_input("Username", value="")
            password = st.text_input("Password", type="password", value="")
            
            st.divider()
            st.header("Scrape Settings")
            mode = st.radio("Mode", ["Last X Games", "Since Date"])
            
            count = st.number_input("Number of games", min_value=1, max_value=500, value=10)
            since = st.date_input("Since Date", value=datetime.now())
            
            st.divider()
            submit_button = st.form_submit_button("🚀 Start Scraping", type="primary", use_container_width=True)

    if submit_button:
        if not username or not password:
            st.error("Please provide both username and password.")
            return

        since_dt = datetime.combine(since, datetime.min.time()) if mode == "Since Date" else None
        limit = count if mode == "Last X Games" else None

        scraper = SauspielScraper(username, password)
        
        with st.status("Initializing...") as status:
            status.update(label=f"Logging in as {username}...", state="running")
            if scraper.login():
                status.update(label="Logged in successfully!", state="running")
            else:
                status.update(label="Login failed!", state="error")
                st.error("Please check your credentials.")
                return

            status.update(label="Fetching game list...", state="running")
            game_list = scraper.get_game_list(limit=limit, since=since_dt)
            total = len(game_list)
            
            if total == 0:
                status.update(label="No games found.", state="complete")
                st.warning("No games found for your user ID.")
                return
                
            status.update(label=f"Found {total} games. Scraping details...", state="running")
            
            progress_bar = st.progress(0)
            progress_text = st.empty()
            
            results = []
            for i, game_info in enumerate(game_list):
                gid = game_info['game_id']
                progress_text.text(f"Scraping Game {gid} ({i+1}/{total})")
                try:
                    game_data = scraper.scrape_game(gid, game_info)
                    results.append(game_data)
                except Exception as e:
                    st.error(f"Error scraping game {gid}: {e}")
                
                progress_bar.progress((i + 1) / total)
            
            status.update(label=f"Scraped {len(results)} games successfully!", state="complete")
            st.session_state["games"] = results

    if st.session_state["games"]:
        st.divider()
        st.subheader(f"Results ({len(st.session_state['games'])} games)")
        
        # Display as JSONL format
        jsonl_text = "\n".join([json.dumps(g, ensure_ascii=False) for g in st.session_state["games"]])
        st.text_area("JSONL Output (Preview)", value=jsonl_text, height=300)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Download JSONL",
                data=jsonl_text,
                file_name=f"sauspiel_games_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl",
                mime="application/jsonl",
                use_container_width=True
            )
        with col2:
            if st.button("🗑️ Clear Results", use_container_width=True):
                st.session_state["games"] = []
                st.rerun()
        
        with st.expander("Inspect Raw JSON"):
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
