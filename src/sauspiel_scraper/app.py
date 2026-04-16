import json
from datetime import datetime

import streamlit as st

from sauspiel_scraper.core import SauspielScraper

# Initialize session state
if "games" not in st.session_state:
    st.session_state["games"] = []
if "scraper" not in st.session_state:
    st.session_state["scraper"] = None

def main() -> None:
    st.set_page_config(page_title="Sauspiel Scraper", page_icon="🎴", layout="centered")
    st.title("🎴 Sauspiel Scraper")

    # --- Sidebar: Authentication ---
    with st.sidebar:
        if st.session_state["scraper"] is None:
            st.header("🔑 Login")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                login_submit = st.form_submit_button("Login", type="primary", use_container_width=True)
                
                if login_submit:
                    if not username or not password:
                        st.error("Please enter credentials.")
                    else:
                        scraper = SauspielScraper(username, password)
                        with st.spinner("Checking credentials..."):
                            if scraper.login():
                                st.session_state["scraper"] = scraper
                                st.rerun()
                            else:
                                st.error("Login failed. Check your credentials.")
        else:
            st.success(f"Logged in as **{st.session_state['scraper'].username}**")
            if st.button("Logout", use_container_width=True):
                st.session_state["scraper"] = None
                st.session_state["games"] = []
                st.rerun()

    # --- Main Area: Scraper Settings ---
    if st.session_state["scraper"] is not None:
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
            scraper = st.session_state["scraper"]
            
            # Reset previous results
            st.session_state["games"] = []
            
            # 1. Fetch game list
            with st.status("Fetching game list...") as status:
                game_list = scraper.get_game_list(limit=count, since=since_dt)
                total = len(game_list)
                if total == 0:
                    status.update(label="No games found.", state="complete")
                    st.warning("No games found for your user ID.")
                    return
                status.update(label=f"Found {total} games. Ready to scrape.", state="complete")

            # 2. Scrape details (always visible)
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

    # --- Main Area: Results ---
    if st.session_state["games"]:
        st.divider()
        st.subheader(f"📦 Results ({len(st.session_state['games'])} games)")
        
        jsonl_text = "\n".join([json.dumps(g, ensure_ascii=False) for g in st.session_state["games"]])
        st.text_area("JSONL Preview", value=jsonl_text, height=300)
        
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
        
        with st.expander("🔍 Inspect Raw JSON"):
            st.json(st.session_state["games"])
    elif st.session_state["scraper"] is None:
        st.info("Please login via the sidebar to start scraping.")

def run_app() -> None:
    import sys
    from streamlit.web import cli as stcli
    from pathlib import Path
    
    app_path = Path(__file__).resolve()
    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
