"""
Coin Universe — Fetches and maintains the list of coins to trade.
Sources:
  1. CoinGecko trending (free, no API key)
  2. Binance top gainers (% change 24h) — momentum filter
  3. Binance top 300 by USDT volume — liquidity filter

Stablecoins, leveraged tokens, and low-quality tokens are excluded.
The coin list is refreshed every 24 hours automatically.
"""

import asyncio
import time
from typing import List, Set
import aiohttp
from loguru import logger
from config import settings

# ── Comprehensive Stablecoin / Bad Token Exclusion List ─────────────────────
STABLECOIN_KEYWORDS = {
    "USDC", "BUSD", "TUSD", "USDP", "FDUSD", "DAI", "FRAX", "USDD",
    "PYUSD", "USD1", "RLUSD", "XUSD", "USDX", "USDE", "EURI", "EUR",
    "GBP", "PAXG", "XAUT", "USDG", "GUSD", "LUSD", "SUSD", "CUSD",
    "HUSD", "MUSD", "AUSD", "USDK", "USDF", "USTC",
}

BAD_TOKEN_SUBSTRINGS = [
    "UP", "DOWN", "BEAR", "BULL", "3L", "3S", "2L", "2S",
    "HEDGE", "SHORT", "LONG", "BVOL", "IBVOL",
]

# Tokens that are clearly stablecoins even without explicit keyword match
EXPLICIT_EXCLUDE = {
    "USDCUSDT", "BUSDUSDT", "TUSDUSDT", "USDPUSDT", "FDUSDUSDT",
    "DAIUSDT", "FRAXUSDT", "EURUSDT", "GBPUSDT", "PAXGUSDT", "XAUTUSDT",
    "USD1USDT", "RLUSDUSDT", "XUSDUSDT", "USDDUSDT", "PYUSDUSDT",
    "EUROUSDT", "EURIUSDT", "WBTCUSDT",  # WBTC is a wrapped token, skip
}


def _is_valid_coin(symbol: str) -> bool:
    """Return True if the symbol is a real tradable coin (not stablecoin/leveraged token)."""
    if symbol in EXPLICIT_EXCLUDE:
        return False
    if not symbol.endswith("USDT"):
        return False
    base = symbol[:-4]  # strip USDT
    if base in STABLECOIN_KEYWORDS:
        return False
    if any(bad in base for bad in BAD_TOKEN_SUBSTRINGS):
        return False
    # Skip very short symbols (likely test tokens)
    if len(base) < 2:
        return False
    return True


# ── Internal Cache ───────────────────────────────────────────────────────────
_cached_coins: List[str] = []
_last_refresh: float = 0.0
REFRESH_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


# ── Source 1: CoinGecko Trending (Free, No Key) ──────────────────────────────
async def _fetch_coingecko_trending() -> Set[str]:
    """Fetch top trending coins from CoinGecko and map to Binance USDT pairs."""
    url = "https://api.coingecko.com/api/v3/search/trending"
    symbols = set()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    coins = data.get("coins", [])
                    for item in coins:
                        ticker = item.get("item", {}).get("symbol", "").upper()
                        if ticker:
                            symbols.add(f"{ticker}USDT")
                    logger.info(f"[CoinGecko] Got {len(symbols)} trending coins")
    except Exception as e:
        logger.warning(f"[CoinGecko] Failed: {e}")
    return symbols


# ── Source 2 + 3: Binance 24h Ticker Data (Futures + Open Vision fallback) ──────
BINANCE_TICKER_ENDPOINTS = [
    "https://fapi.binance.com/fapi/v1/ticker/24hr",
    "https://fapi1.binance.com/fapi/v1/ticker/24hr",
    "https://data-api.binance.vision/api/v3/ticker/24hr",
    "https://api.binance.com/api/v3/ticker/24hr",
]


async def _fetch_binance_tickers() -> list:
    """Fetch 24h ticker data from Binance endpoints with automatic fallback."""
    for url in BINANCE_TICKER_ENDPOINTS:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list) and len(data) > 50:
                            return data
        except Exception:
            continue
    return []


async def fetch_top_coins(n: int = 300) -> List[str]:
    """
    Build the full coin trading universe:
    - CoinGecko trending coins (momentum/hype)
    - Binance top 50 gainers by % change (trending movers)
    - Binance top N by quote volume (liquidity)
    Combined, deduplicated, and filtered.
    """
    logger.info(f"Refreshing coin universe (target: {n} coins)...")

    # Fetch sources concurrently
    trending_task = asyncio.create_task(_fetch_coingecko_trending())
    tickers = await _fetch_binance_tickers()
    trending_symbols = await trending_task

    if not tickers:
        logger.warning("Binance tickers unavailable — using fallback coin list")
        return _fallback_coins(n)

    # Filter to valid USDT pairs only
    valid = [t for t in tickers if _is_valid_coin(t.get("symbol", ""))]

    # Minimum volume threshold — skip ghost/illiquid coins
    valid = [t for t in valid if float(t.get("quoteVolume", 0)) > 500_000]

    # ── Bucket 1: Top gainers (trending momentum) ────────────────────────────
    gainers = sorted(valid, key=lambda x: float(x.get("priceChangePercent", 0)), reverse=True)
    gainer_symbols = {t["symbol"] for t in gainers[:60]}

    # ── Bucket 2: Top volume (most liquid) ──────────────────────────────────
    by_volume = sorted(valid, key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
    volume_symbols = {t["symbol"] for t in by_volume[:n]}

    # ── Combine: CoinGecko trending + gainers + top volume ───────────────────
    # Priority order: trending first, then gainers, then volume
    all_symbols: List[str] = []

    # Add trending (from CoinGecko) first if they exist on Binance
    binance_symbol_set = {t["symbol"] for t in valid}
    for sym in trending_symbols:
        if sym in binance_symbol_set and sym not in all_symbols:
            all_symbols.append(sym)

    # Add top gainers
    for sym in (gainer_symbols - set(all_symbols)):
        all_symbols.append(sym)

    # Fill remainder with top volume
    for sym in (volume_symbols - set(all_symbols)):
        all_symbols.append(sym)

    # Final filter pass and cap
    result = [s for s in all_symbols if _is_valid_coin(s)][:n]

    logger.success(f"[OK] Coin universe: {len(result)} coins (trending: {len(trending_symbols & binance_symbol_set)}, gainers: {len(gainer_symbols)}, volume: {len(volume_symbols)})")
    return result


def _fallback_coins(n: int = 50) -> List[str]:
    """Static fallback list of top liquid coins if all APIs fail."""
    base = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "SHIBUSDT", "DOTUSDT",
        "LINKUSDT", "NEARUSDT", "SUIUSDT", "PEPEUSDT", "LTCUSDT",
        "UNIUSDT", "APTUSDT", "FETUSDT", "TAOUSDT", "TRXUSDT",
        "INJUSDT", "ARBUSDT", "OPUSDT", "ATOMUSDT", "MATICUSDT",
        "AAVEUSDT", "MKRUSDT", "GMXUSDT", "LRCUSDT", "ICPUSDT",
        "FILUSDT", "HBARUSDT", "XLMUSDT", "ALGOUSDT", "VETUSDT",
        "SANDUSDT", "MANAUSDT", "AXSUSDT", "APEUSDT", "GALAUSDT",
    ]
    return base[:n]


# ── Public API ───────────────────────────────────────────────────────────────
async def get_coin_universe() -> List[str]:
    """Returns cached coin list, fetching fresh if empty."""
    global _cached_coins
    if not _cached_coins:
        _cached_coins = await fetch_top_coins(settings.TOP_N_COINS)
    return _cached_coins


async def refresh_coin_universe() -> List[str]:
    """Force-refresh the coin universe and update the cache + timestamp."""
    global _cached_coins, _last_refresh
    _cached_coins = await fetch_top_coins(settings.TOP_N_COINS)
    _last_refresh = time.time()
    return _cached_coins


async def maybe_refresh_coin_universe() -> bool:
    """Refresh coin universe if 24 hours have passed. Returns True if refreshed."""
    global _last_refresh
    if time.time() - _last_refresh >= REFRESH_INTERVAL_SECONDS:
        logger.info("[Coin Universe] 24h refresh triggered...")
        await refresh_coin_universe()
        return True
    return False


def coin_universe_age_hours() -> float:
    """How many hours since the last coin universe refresh."""
    if _last_refresh == 0:
        return 999.0
    return (time.time() - _last_refresh) / 3600
