import os
from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import dotenv
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from sauspiel_scraper.app.analytics import process_game_data, render_analytics
from sauspiel_scraper.app.auth import decrypt_password, encrypt_password
from sauspiel_scraper.core import SauspielScraper
from sauspiel_scraper.rate_limiter import RateLimiter
from sauspiel_scraper.repository import Database

# Setup
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
db = Database()
global_rate_limiter = RateLimiter()
scheduler = BackgroundScheduler()
active_scrapes = {}

dotenv.load_dotenv()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a SQLAlchemy session.
    """
    with db.Session() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler.start()
    # Schedule the task to run every 6 hours
    scheduler.add_job(scrape_all_users, "interval", hours=6, id="scrape_all")
    print("Scheduler started and job added.")
    yield
    # Shutdown
    scheduler.shutdown()
    print("Scheduler shut down.")


app = FastAPI(title="Sauspiel Scraper", lifespan=lifespan)
# Add session middleware for signed cookies
app.add_middleware(
    SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "local-dev-secret-change-me")
)


def scrape_all_users(username: str | None = None):
    """
    Background task to scrape games for one or all users.
    """
    with db.session_scope() as session:
        usernames = [username] if username else db.get_all_users(session=session)

        for uname in usernames:
            user_data = db.get_user(uname, session=session)
            if not user_data or not user_data.get("encrypted_password"):
                continue

            try:
                password = decrypt_password(user_data["encrypted_password"])
                scraper = SauspielScraper(uname, password, rate_limiter=global_rate_limiter)

                if scraper.login():
                    # Fetch new game previews for the current month only
                    first_of_month = datetime.now().replace(
                        day=1, hour=0, minute=0, second=0, microsecond=0
                    )
                    new_games = scraper.get_game_list_paginated(
                        max_new=100, since=first_of_month, db=db
                    )

                    count = 0
                    for info in new_games:
                        try:
                            data = scraper.scrape_game(info.game_id, info)
                            if data:
                                db.save_game(data, session=session)
                                count += 1
                        except Exception as e:
                            print(f"Error scraping game {info.game_id} for {uname}: {e}")

                    db.update_last_scraped(uname, datetime.now().isoformat(), session=session)
                    print(f"Successfully scraped {count} new games for {uname}")
                else:
                    print(f"Login failed for {uname} during background scrape")
            except Exception as e:
                print(f"Error in background scrape for {uname}: {e}")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_db)):
    username = request.session.get("username")

    games = []
    charts = {}
    if username:
        raw_games = db.get_all_games(username=username, session=session)
        processed_games = process_game_data(raw_games, username)
        games = processed_games
        charts = render_analytics(processed_games)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": username, "games": games, "charts": charts},
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"user": None})


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_db),
):
    scraper = SauspielScraper(username, password, rate_limiter=global_rate_limiter)
    if scraper.login():
        # Success: encrypt password and save user
        enc_pass = encrypt_password(password)
        db.save_user(username, enc_pass, session=session)

        # Store in signed session instead of raw cookie
        request.session["username"] = username
        return RedirectResponse(url="/", status_code=303)
    else:
        # Failure: back to login with error
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"user": None, "error": "Login failed. Please check your credentials."},
        )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.post("/scrape")
def trigger_scrape(request: Request):
    username = request.session.get("username")
    if not username:
        return HTMLResponse("Not logged in", status_code=401)

    job_id = f"manual_{username}"
    if job_id in active_scrapes:
        return HTMLResponse("<span>Scrape already in progress...</span>")

    def scrape_wrapper(uname):
        try:
            scrape_all_users(uname)
        finally:
            active_scrapes.pop(f"manual_{uname}", None)

    active_scrapes[job_id] = datetime.now()
    scheduler.add_job(scrape_wrapper, args=[username], id=job_id)

    return HTMLResponse("""
        <div hx-get="/scrape/status" hx-trigger="every 2s" hx-target="this" hx-swap="outerHTML">
            🚀 Scrape triggered...
        </div>
    """)


@app.get("/scrape/status")
def scrape_status(request: Request):
    username = request.session.get("username")
    job_id = f"manual_{username}"

    if job_id in active_scrapes:
        return HTMLResponse(f"""
            <div hx-get="/scrape/status" hx-trigger="every 5s" hx-target="this" hx-swap="outerHTML">
                ⏳ Scraping in progress (started {active_scrapes[job_id].strftime("%H:%M:%S")})...
            </div>
        """)
    else:
        return HTMLResponse("""
            <div hx-get="/" hx-target="body" hx-trigger="load">
                ✅ Scrape finished! Refreshing dashboard...
            </div>
        """)


def run_app() -> None:
    """
    Entry point for the FastAPI application.
    """
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("sauspiel_scraper.app.main:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    run_app()
