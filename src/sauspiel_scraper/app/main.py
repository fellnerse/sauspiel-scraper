from datetime import datetime
from pathlib import Path

import streamlit as st

from sauspiel_scraper.app.analytics import process_game_data, render_analytics
from sauspiel_scraper.core import SauspielScraper
from sauspiel_scraper.repository import Database

DB_FILE = Path("output/sauspiel.db")
SESSION_FILE = Path("output/session.json")


def main() -> None:
    st.set_page_config(page_title="Sauspiel Scraper", page_icon="🎴", layout="wide")

    if "scraper" not in st.session_state:
        st.session_state["scraper"] = SauspielScraper.from_session_file(SESSION_FILE)
    if "db" not in st.session_state:
        st.session_state["db"] = Database()

    scraper, db = st.session_state["scraper"], st.session_state["db"]

    st.title("🎴 Sauspiel Scraper & Analytics")

    with st.sidebar:
        if st.session_state["scraper"] is None:
            st.header("🔑 Login")
            with st.form("login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login", type="primary", width="stretch"):
                    s = SauspielScraper(u, p)
                    if s.login():
                        st.session_state["scraper"] = s
                        s.save_session(SESSION_FILE)
                        st.rerun()
                    else:
                        st.error("Login failed.")
        else:
            st.success(f"Logged in: **{st.session_state['scraper'].username}**")
            if st.button("Logout", width="stretch"):
                st.session_state["scraper"] = None
                if SESSION_FILE.exists():
                    SESSION_FILE.unlink()
                st.rerun()

            all_games = db.get_all_games()
            if all_games:
                st.divider()
                st.header("📥 Export")
                jsonl_data = "\n".join([g.model_dump_json(exclude_unset=True) for g in all_games])
                st.download_button(
                    label="Download All Data (JSONL)",
                    data=jsonl_data,
                    file_name=f"sauspiel_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl",
                    mime="application/x-jsonlines",
                )

            st.divider()
            st.header("🗑️ Data Management")
            if st.button("Clear Database", type="secondary", width="stretch"):
                if DB_FILE.exists():
                    DB_FILE.unlink()
                    st.session_state["db"] = Database()
                    st.success("Database cleared!")
                    st.rerun()

    if st.session_state["scraper"] is None:
        st.info("Please login in the sidebar.")
        return

    st.header("⚙️ Fetch New Games")
    c1, c2 = st.columns(2)
    with c1:
        mode = st.radio("Mode", ["Next X new games", "All since date"], horizontal=True)
    with c2:
        if mode == "Next X new games":
            val = st.number_input("Count", min_value=1, max_value=1000, value=20)
            since = None
        else:
            dt = st.date_input("Date")
            since = datetime.combine(dt, datetime.min.time())
            val = 2000

    # Permanent progress placeholders
    p_bar_area = st.empty()
    p_text_area = st.empty()

    if st.button("🚀 Run Scraper", type="primary", width="stretch"):
        with st.status("Checking history...") as status:
            new_list = scraper.get_game_list_paginated(max_new=int(val), since=since, db=db)
            if not new_list:
                status.update(label="No new games found!", state="complete")
                st.info("Everything is up to date.")
            else:
                status.update(
                    label=f"Found {len(new_list)} new games. Scraping...", state="running"
                )

                pb = p_bar_area.progress(0)
                scraped_count = 0
                for i, info in enumerate(new_list):
                    gid = info.game_id
                    p_text_area.markdown(f"Scraping `{gid}` ({i + 1}/{len(new_list)})")

                    def st_log(msg: str) -> None:
                        st.toast(msg)

                    try:
                        data = scraper.scrape_game(gid, info, log_func=st_log)
                        db.save_game(data)
                        scraped_count += 1
                    except Exception as e:
                        st.error(f"Error {gid}: {e}")
                    pb.progress((i + 1) / len(new_list))

                status.update(label=f"Done! Added {scraped_count} new games.", state="complete")
                p_text_area.success(f"Added {scraped_count} new games to database.")
                st.balloons()

    all_games = db.get_all_games()
    if all_games:
        df = process_game_data(all_games, scraper.username)
        st.divider()
        render_analytics(df)
    else:
        st.info("Database empty.")


if __name__ == "__main__":
    main()
