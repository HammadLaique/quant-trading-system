"""
Main FastAPI Application.
Entry point for the Quant Trading System backend.
"""

import asyncio
import sys
import os
import io

# ─── UTF-8 Fix for Windows terminals (must be before any logging setup) ────────
# This prevents UnicodeEncodeError when printing emojis to Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from config import settings
from api.routes import router
from api.ws_handler import websocket_endpoint
from core.strategy_runner import runner


# In Docker: main.py lives at /app/main.py, so BASE_DIR = /app
# Locally: main.py lives at backend/main.py, so BASE_DIR = backend/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Ensure critical directories exist ───────────────────────────────────────
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
os.makedirs(settings.MODELS_DIR, exist_ok=True)


# ─── Configure Logging ───────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)
logger.add(
    os.path.join(BASE_DIR, "logs", "trading_{time:YYYY-MM-DD}.log"),
    rotation="00:00",
    retention="30 days",
    level="DEBUG",
    enqueue=True,
)


# ─── Application Lifespan ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("=" * 60)
    logger.info("QUANT TRADING SYSTEM STARTING")
    logger.info(f"  Initial balance : ${settings.INITIAL_BALANCE_USDT:,.0f} USDT")
    logger.info(f"  Default leverage: {settings.DEFAULT_LEVERAGE}x")
    logger.info(f"  Max leverage    : {settings.MAX_LEVERAGE}x")
    logger.info(f"  Risk per trade  : {settings.RISK_PER_TRADE_PERCENT}%")
    logger.info(f"  Top N coins     : {settings.TOP_N_COINS}")
    logger.info(f"  ML threshold    : {settings.WIN_PROB_THRESHOLD}")
    logger.info("=" * 60)

    # Start strategy runner in background
    runner_task = asyncio.create_task(runner.start())

    yield  # App is running

    # Shutdown
    logger.info("Shutting down trading system...")
    await runner.stop()
    runner_task.cancel()
    try:
        await runner_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutdown complete.")


# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Quant Trading System API",
    description="Autonomous crypto trading bot with ML-enhanced signals across top 100 coins",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend (localhost:3000 dev + Vercel production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
        settings.FRONTEND_URL,
        "*",  # Allow all origins in dev mode
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(router, prefix="/api")


# WebSocket endpoint
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket_endpoint(websocket)


# ─── Run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level="warning",   # Let loguru handle our log output
    )

