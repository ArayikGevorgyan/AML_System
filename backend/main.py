from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from database import create_tables


def _run_daily_seed():
    try:
        from scripts.seed_today import seed_today
        seed_today()
    except Exception as e:
        print(f"[Scheduler] Daily seed failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    print("[AML] Database tables ready.")

    try:
        from database import SessionLocal
        from models.transaction import Transaction
        from datetime import datetime, timezone
        db = SessionLocal()
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = db.query(Transaction).filter(Transaction.created_at >= today).count()
        db.close()
        if count < 10:
            print("[AML] Fewer than 10 transactions today — running startup seed...")
            _run_daily_seed()
    except Exception as e:
        print(f"[AML] Startup seed check failed: {e}")

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_daily_seed,
        CronTrigger(hour=8, minute=0),
        id="daily_seed",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    print("[AML] Scheduler started — daily seed at 08:00.")

    yield

    scheduler.shutdown(wait=False)
    print("[AML] Shutdown.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "null",
    ],
    allow_origin_regex=r"file://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import (
    auth, customers, transactions, rules, alerts, cases,
    sanctions, dashboard, audit, blacklist, escalation,
    reporting, risk_scoring,
)
from routers import sessions as sessions_router
from routers import export_router
from routers import demo as demo_router
from models.session import UserSession

app.include_router(auth.router,         prefix="/api/v1")
app.include_router(customers.router,    prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(rules.router,        prefix="/api/v1")
app.include_router(alerts.router,       prefix="/api/v1")
app.include_router(cases.router,        prefix="/api/v1")
app.include_router(sanctions.router,    prefix="/api/v1")
app.include_router(dashboard.router,    prefix="/api/v1")
app.include_router(audit.router,        prefix="/api/v1")
app.include_router(blacklist.router,    prefix="/api/v1")
app.include_router(escalation.router,   prefix="/api/v1")
app.include_router(reporting.router,    prefix="/api/v1")
app.include_router(risk_scoring.router, prefix="/api/v1")
app.include_router(sessions_router.router, prefix="/api/v1")
app.include_router(export_router.router,   prefix="/api/v1")
app.include_router(demo_router.router,     prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {
        "system": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
