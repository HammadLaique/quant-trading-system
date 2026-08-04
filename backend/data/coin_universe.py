"""
Fetches and maintains the universe of top N coins by 24h USDT volume on Binance.
Includes robust fallback for cloud hosting environments.
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

# Standard liquid top coins fallback (used if Binance REST API blocks cloud server IPs)
DEFAULT_COINS_FALLBACK = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "SHIBUSDT", "DOTUSDT",
    "LINKUSDT", "NEARUSDT", "SUIUSDT", "PEPEUSDT", "LTCUSDT",
    "UNIUSDT", "APTUSDT", "FETUSDT", "TAOUSDT", "TRXUSDT"
]


async def fetch_top_coins(n: int = 100) -> List[str]:
    """
    Fetch the top N USDT-quoted coins by 24h quote volume from Binance.
    Falls back gracefully if Binance REST API fails.
    """
    url = f"{settings.BINANCE_REST_URL}/api/v3/ticker/24hr"
    logger.info(f"Fetching top {n} coins by 24h volume from Binance...")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    tickers = await resp.json()
                    usdt_pairs = [
                        t for t in tickers
                        if t["symbol"].endswith("USDT")
                        and t["symbol"] not in EXCLUDE_SYMBOLS
                        and not any(bad in t["symbol"] for bad in ["UP", "DOWN", "BEAR", "BULL"])
                    ]
                    usdt_pairs.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
                    top_symbols = [t["symbol"] for t in usdt_pairs[:n]]
                    if top_symbols:
                        logger.success(f"[OK] Top {len(top_symbols)} coins selected from Binance REST API")
                        return top_symbols
                else:
                    logger.warning(f"Binance API returned status {resp.status}. Using top coin fallback list.")
    except Exception as e:
        logger.warning(f"Binance REST API fetch error ({e}). Using top coin fallback list.")

    fallback = DEFAULT_COINS_FALLBACK[:n]
    logger.success(f"[OK] Using fallback universe of {len(fallback)} top coins")
    return fallback


# Cached list
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
