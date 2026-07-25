"""
Fetches and maintains the universe of top N coins by 24h USDT volume on Binance.
"""

import aiohttp
from loguru import logger
from typing import List
from config import settings

# Coins to explicitly exclude (stablecoins, leveraged tokens, etc.)
EXCLUDE_SYMBOLS = {
    "USDCUSDT", "BUSDUSDT", "TUSDUSDT", "USDPUSDT", "FDUSDUSDT",
    "DAIUSDT", "FRAXUSDT", "EURUSDT", "GBPUSDT",
    "BTCUPUSDT", "BTCDOWNUSDT", "ETHUPUSDT", "ETHDOWNUSDT",
    "BNBUPUSDT", "BNBDOWNUSDT", "ADAUPUSDT", "ADADOWNUSDT",
}


async def fetch_top_coins(n: int = 100) -> List[str]:
    """
    Fetch the top N USDT-quoted coins by 24h quote volume from Binance.
    Returns a list of symbols like ['BTCUSDT', 'ETHUSDT', ...]
    """
    url = f"{settings.BINANCE_REST_URL}/api/v3/ticker/24hr"
    logger.info(f"Fetching top {n} coins by 24h volume from Binance...")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Binance API error: {resp.status}")
            tickers = await resp.json()

    # Filter for USDT pairs only, exclude bad tokens
    usdt_pairs = [
        t for t in tickers
        if t["symbol"].endswith("USDT")
        and t["symbol"] not in EXCLUDE_SYMBOLS
        and not any(bad in t["symbol"] for bad in ["UP", "DOWN", "BEAR", "BULL"])
    ]

    # Sort by 24h quote volume (descending)
    usdt_pairs.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)

    # Take top N
    top_symbols = [t["symbol"] for t in usdt_pairs[:n]]

    logger.success(f"[OK] Top {len(top_symbols)} coins selected")
    logger.debug(f"Coins: {', '.join(top_symbols[:10])} ...")
    return top_symbols


# Cached list (refreshed periodically by the strategy runner)
_cached_coins: List[str] = []


async def get_coin_universe() -> List[str]:
    """Returns cached coin list, or fetches fresh if empty."""
    global _cached_coins
    if not _cached_coins:
        _cached_coins = await fetch_top_coins(settings.TOP_N_COINS)
    return _cached_coins


async def refresh_coin_universe() -> List[str]:
    """Force refresh the coin universe."""
    global _cached_coins
    _cached_coins = await fetch_top_coins(settings.TOP_N_COINS)
    return _cached_coins

