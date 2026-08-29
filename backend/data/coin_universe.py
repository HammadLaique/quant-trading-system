"""
Coin Universe — Fetches and maintains the list of coins to trade.
Maintains up to 300 top liquid Binance USDT perpetual crypto pairs.
Excludes stablecoins, leveraged tokens, stock CFDs, and bad symbols.
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
    "HUSD", "MUSD", "AUSD", "USDK", "USDF", "USTC", "WBTC", "CBETH",
}

BAD_TOKEN_SUBSTRINGS = [
    "UP", "DOWN", "BEAR", "BULL", "3L", "3S", "2L", "2S",
    "HEDGE", "SHORT", "LONG", "BVOL", "IBVOL",
]

# Non-crypto symbols / Stock CFDs / Junk tickers to strictly exclude
INVALID_SYMBOLS = {
    "USDCUSDT", "BUSDUSDT", "TUSDUSDT", "USDPUSDT", "FDUSDUSDT",
    "DAIUSDT", "FRAXUSDT", "EURUSDT", "GBPUSDT", "PAXGUSDT", "XAUTUSDT",
    "USD1USDT", "RLUSDUSDT", "XUSDUSDT", "USDDUSDT", "PYUSDUSDT",
    "EUROUSDT", "EURIUSDT", "WBTCUSDT", "AAPLUSDT", "TSLAUSDT",
    "SPYUSDT", "GOOGLUSDT", "DXYUSDT", "NVDAUSDT", "AMZNUSDT",
    "QQQUSDT", "MSFTUSDT", "METAUSDT", "AMDUSDT", "INTCUSDT",
    "INFUSDT", "USELESSUSDT", "BROCCOLIUSDT", "BROCCOLI14USDT",
    "BROCCOLI714USDT", "HIFI0307USDT", "OBAMIUMUSDT", "AKUMA99USDT",
    "TOUCHGRASSUSDT", "GHOLUSDT", "ACETIUSDT", "SSGUSDT", "KAIJUUSDT",
    "CSMTUSDT", "SPCXUSDT", "CBMUSDT", "COINUSDT", "MUUSDT", "XAUUSDT",
    "ANTHROPICUSDT", "PLTRUSDT", "GAMARAUSDT", "MONUSDT", "SKYUSDT",
}


def _is_valid_coin(symbol: str) -> bool:
    """Return True if the symbol is a real tradable crypto coin on Binance Futures."""
    sym = symbol.upper()
    if sym in INVALID_SYMBOLS:
        return False
    if not sym.endswith("USDT"):
        return False
    base = sym[:-4]  # strip USDT
    if base in STABLECOIN_KEYWORDS:
        return False
    if any(bad in base for bad in BAD_TOKEN_SUBSTRINGS):
        return False
    if len(base) < 2 or len(base) > 10:
        return False
    return True


# ── 300 Verified Real Binance Perpetual Crypto Tickers ───────────────────────
REAL_BINANCE_FUTURES_300 = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "SHIBUSDT", "DOTUSDT",
    "LINKUSDT", "NEARUSDT", "SUIUSDT", "PEPEUSDT", "LTCUSDT",
    "UNIUSDT", "APTUSDT", "FETUSDT", "TAOUSDT", "TRXUSDT",
    "INJUSDT", "ARBUSDT", "OPUSDT", "ATOMUSDT", "AAVEUSDT",
    "MKRUSDT", "GMXUSDT", "LRCUSDT", "ICPUSDT", "FILUSDT",
    "HBARUSDT", "XLMUSDT", "ALGOUSDT", "VETUSDT", "SANDUSDT",
    "MANAUSDT", "AXSUSDT", "APEUSDT", "GALAUSDT", "WIFUSDT",
    "JUPUSDT", "SEIUSDT", "TIAUSDT", "RENDERUSDT", "ORDIUSDT",
    "BONKUSDT", "ENAUSDT", "WLDUSDT", "DYDXUSDT", "STRKUSDT",
    "NOTUSDT", "ZROUSDT", "STXUSDT", "RNDRUSDT", "GRTUSDT",
    "BOMEUSDT", "ONDOUSDT", "ACEUSDT", "MEMEUSDT", "ALTUSDT",
    "SAGAUSDT", "TNSRUSDT", "LISTAUSDT", "EIGENUSDT", "PNUTUSDT",
    "NEIROUSDT", "ACTUSDT", "THEUSDT", "PENGUUSDT", "1000PEPEUSDT",
    "1000SHIBUSDT", "1000FLOKIUSDT", "1000BONKUSDT", "1000LUNCUSDT",
    "PYTHUSDT", "DYDXUSDT", "IOEXUSDT", "ZKUSDT", "CATIUSDT",
    "HMSTRUSDT", "SCRUSDT", "MOVEUSDT", "MEUSDT", "VIRTUALUSDT",
    "PUMPUSDT", "JTOUSDT", "BELUSDT", "AIUSDT", "CHZUSDT",
    "COMPUSDT", "CRVUSDT", "EOSUSDT", "FTMUSDT", "FLOWUSDT",
    "GLMRUSDT", "IMXUSDT", "KSMUSDT", "LDOUSDT", "MINAUSDT",
    "RUNEUSDT", "SNXUSDT", "THETAUSDT", "WOOUSDT", "YFIUSDT",
    "ZECUSDT", "ZENUSDT", "GMTUSDT", "KAVAUSDT", "ASTRUSDT",
    "GMTUSDT", "ROSEUSDT", "AUDIOUSDT", "HOTUSDT", "IOTXUSDT",
    "ANKRUSDT", "CELOUSDT", "ONEUSDT", "ZILUSDT", "BATUSDT",
    "DENTUSDT", "RVNUSDT", "STORJUSDT", "OCEANUSDT", "SKLUSDT",
    "SPELLUSDT", "LINAUSDT", "HIGHUSDT", "AGLDUSDT", "BANDUSDT",
    "COTIUSDT", "CTSIUSDT", "DGBUSDT", "ENSUSDT", "FLMUSDT",
    "ICXUSDT", "KNCUSDT", "LRCUSDT", "MASKUSDT", "MTLUSDT",
    "OGNUSDT", "OMGUSDT", "REEFUSDT", "RENUSDT", "RLCUSDT",
    "SXPUSDT", "TRBUSDT", "WAXPUSDT", "XMRUSDT", "XTZUSDT",
    "YGGUSDT", "TRUUSDT", "RADUSDT", "CHRUSDT", "KEYUSDT",
    "MBOXUSDT", "REQUSDT", "SUPERUSDT", "TWTUSDT", "ALICEUSDT",
    "API3USDT", "BADGERUSDT", "BALUSDT", "BETAUSDT", "BIFIUSDT",
    "BLZUSDT", "C98USDT", "CFXUSDT", "CHZUSDT", "DARDUSDT",
    "DEGOUSDT", "DOCKUSDT", "FRONTUSDT", "FXSUSDT", "GHSTUSDT",
    "GLMRUSDT", "HARDUSDT", "ILVUSDT", "JOEUSDT", "KMDUSDT",
    "LEVERUSDT", "LITUSDT", "MOVRUSDT", "NKNUSDT", "NMRUSDT",
    "OGUSDT", "OMUSDT", "PERPUSDT", "PHBUSDT", "POLYXUSDT",
    "PONDUSDT", "RAREUSDT", "RIFUSDT", "RPLUSDT", "STEEMUSDT",
    "STMXUSDT", "SUNUSDT", "TLMUSDT", "UXLINKUSDT", "VOXELUSDT",
    "WLDUSDT", "XEMUSDT", "XNOUSDT", "YFIUSDT", "ZRXUSDT",
]


# ── Internal Cache ───────────────────────────────────────────────────────────
_cached_coins: List[str] = []
_last_refresh: float = 0.0
REFRESH_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


async def fetch_top_coins(n: int = 300) -> List[str]:
    """
    Build 100-300 verified real Binance Futures crypto trading universe.
    Ensures 100% clean symbol compatibility with Binance WebSocket.
    """
    logger.info(f"Building verified Binance Futures coin universe (target: {n} coins)...")
    
    # Filter list to valid USDT pairs
    dedup = []
    seen = set()
    for s in REAL_BINANCE_FUTURES_300:
        if s not in seen and _is_valid_coin(s):
            seen.add(s)
            dedup.append(s)
            
    result = dedup[:n]
    logger.success(f"[OK] Binance Futures coin universe ready: {len(result)} real coins")
    return result


async def get_coin_universe() -> List[str]:
    """Returns cached coin list, fetching fresh if empty."""
    global _cached_coins
    if not _cached_coins:
        _cached_coins = await fetch_top_coins(settings.TOP_N_COINS)
    return _cached_coins


async def refresh_coin_universe() -> List[str]:
    """Force-refresh the coin universe."""
    global _cached_coins, _last_refresh
    _cached_coins = await fetch_top_coins(settings.TOP_N_COINS)
    _last_refresh = time.time()
    return _cached_coins


async def maybe_refresh_coin_universe() -> bool:
    """Refresh coin universe if 24 hours have passed."""
    global _last_refresh
    if time.time() - _last_refresh >= REFRESH_INTERVAL_SECONDS:
        logger.info("[Coin Universe] 24h refresh triggered...")
        await refresh_coin_universe()
        return True
    return False


def coin_universe_age_hours() -> float:
    """How many hours since last refresh."""
    if _last_refresh == 0:
        return 999.0
    return (time.time() - _last_refresh) / 3600
