"""
One-time script to pre-train ML models for all top 100 coins.
This avoids long startup delays for the live trading system.
"""

import asyncio
import os
import sys
from loguru import logger

# Add backend directory to sys.path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from config import settings
from data.coin_universe import fetch_top_coins
from data.binance_client import fetch_klines_full
from ml.trainer import train_model_for_symbol, model_exists


async def train_coin(symbol: str):
    """Fetch data and train model for a single coin."""
    if model_exists(symbol):
        logger.info(f"[{symbol}] Model already exists. Skipping.")
        return True

    try:
        df_hist = await fetch_klines_full(
            symbol,
            interval=settings.TIMEFRAME,
            days=settings.HISTORICAL_DAYS,
        )

        if df_hist.empty or len(df_hist) < 1000:
            logger.warning(f"[{symbol}] Insufficient data fetched ({len(df_hist)} rows). Skipping.")
            return False

        # Train model
        result = train_model_for_symbol(df_hist, symbol)
        if result:
            logger.success(f"[{symbol}] Model trained successfully!")
            return True
        else:
            logger.warning(f"[{symbol}] Model training returned None.")
            return False

    except Exception as e:
        logger.error(f"[{symbol}] Exception during training: {e}")
        return False


async def main():
    logger.info("Starting model training for top coins...")
    os.makedirs(settings.MODELS_DIR, exist_ok=True)

    # 1. Determine target coins
    if len(sys.argv) > 1:
        coins = [arg.upper() for arg in sys.argv[1:]]
        logger.info(f"Target coins specified via CLI: {coins}")
    else:
        try:
            coins = await fetch_top_coins(settings.TOP_N_COINS)
            logger.info(f"Loaded top {len(coins)} coins from Binance.")
        except Exception as e:
            logger.critical(f"Failed to fetch top coins: {e}")
            return

    logger.info(f"Starting training for {len(coins)} coins...")

    # 2. Train coins in small batches to respect rate limits and manage resources
    batch_size = 3
    for i in range(0, len(coins), batch_size):
        batch = coins[i : i + batch_size]
        logger.info(f"--- Training Batch {i // batch_size + 1} / {(len(coins) - 1) // batch_size + 1}: {batch} ---")
        tasks = [train_coin(symbol) for symbol in batch]
        await asyncio.gather(*tasks)
        await asyncio.sleep(2)  # Pause to let the rate limit rest and CPU cool down

    logger.success("🎉 Model training processes completed!")


if __name__ == "__main__":
    asyncio.run(main())
