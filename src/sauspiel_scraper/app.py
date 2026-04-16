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
DB_FILE = Path("output/sauspiel.db")


def save_session(scraper: SauspielScraper) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(scraper.get_session_data(), f)


def load_stored_session() -> SauspielScraper | None:
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE) as f:
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

        # Enhanced role logic: check 'roles' dict, fallback to title
        roles_dict = g.get("roles", {})
        if roles_dict and me in roles_dict:
            role = roles_dict[me]
        else:
            # Fallback for old data in DB
            title = g.get("title") or ""
            role = "Spieler" if f"von {me}" in title else "Gegenspieler"

        # Identify the declarer from the title "GameType von Username"
        title = g.get("title") or ""
        declarer = "Unknown"
        if " von " in title:
            declarer = title.split(" von ")[-1].strip()

        raw_laufende = meta.get("laufende", "0")
        laufende = 0
        try:
            laufende = int(re.sub(r"[^\d]", "", raw_laufende))
        except Exception:
            pass

        rows.append(
            {
                "game_id": g.get("game_id"),
                "date": pd.to_datetime(meta.get("date")),
                "type": g.get("game_type", "Unknown"),
                "declarer": declarer,
                "won": won,
                "value": val if won else -val,
                "role": role,
                "laufende": laufende,
                "location": meta.get("location", "Unknown"),
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
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="Sauspiel Scraper", page_icon="🎴", layout="wide")

    if "scraper" not in st.session_state:
        st.session_state["scraper"] = load_stored_session()
    if "db" not in st.session_state:
        st.session_state["db"] = Database()

    scraper, db = st.session_state["scraper"], st.session_state["db"]
    all_games = db.get_all_games()
    df = (
        process_game_data(all_games, scraper.username)
        if all_games and scraper
        else pd.DataFrame()
    )

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
                        save_session(s)
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

            if all_games:
                st.divider()
                st.header("📥 Export")
                jsonl_data = "\n".join(
                    [json.dumps(g, ensure_ascii=False) for g in all_games]
                )
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
                    gid = info["game_id"]
                    p_text_area.markdown(f"Scraping `{gid}` ({i + 1}/{len(new_list)})")

                    def st_log(msg: str) -> None:
                        st.toast(msg)

                    try:
                        data = scraper.scrape_game(gid, info, log_func=st_log)
                        db.save_game(gid, info.get("date", ""), data.get("game_type", ""), data)
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


def run_app() -> None:
    import sys

    from streamlit.web import cli as stcli

    app_path = Path(__file__).resolve()
    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
