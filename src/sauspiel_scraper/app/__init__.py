import sys
from pathlib import Path

from streamlit.web import cli as stcli


def run_app() -> None:
    """
    Entry point for the Streamlit application.
    This starts the Streamlit server pointing to our main dashboard.
    """
    # Path(__file__) is src/sauspiel_scraper/app/__init__.py
    app_path = Path(__file__).parent / "main.py"
    sys.argv = ["streamlit", "run", str(app_path.resolve())]
    sys.exit(stcli.main())
