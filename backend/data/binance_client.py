"""
Binance public data client.
- REST: fetch historical klines (no API key required)
- WebSocket: subscribe to live 1-minute kline streams
Includes multi-domain fallback for cloud hosting environments.
"""

import asyncio
import json
import time
from typing import Callable, Dict, List, Optional
import aiohttp
import websockets
import pandas as pd
import numpy as np
from loguru import logger
from config import settings


BINANCE_REST_ENDPOINTS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
]


async def fetch_klines(
    symbol: str,
    interval: str = "1m",
    limit: int = 1000,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> pd.DataFrame:
    """
    Fetch historical klines from Binance REST API trying fast endpoints with 1.5s timeout.
    """
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time

    for base_url in BINANCE_REST_ENDPOINTS:
        url = f"{base_url}/api/v3/klines"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1.5)) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and isinstance(data, list):
                            return _klines_to_df(data)
        except Exception:
            continue

    return pd.DataFrame()


async def fetch_klines_full(
    symbol: str,
    interval: str = "1m",
    days: int = 90,
) -> pd.DataFrame:
    """
    Fetch multiple pages of klines to cover `days` of history.
    """
    all_dfs: List[pd.DataFrame] = []
    end_time = int(time.time() * 1000)
    interval_ms = _interval_to_ms(interval)
    start_time = end_time - (days * 24 * 60 * 60 * 1000)

    logger.info(f"[{symbol}] Fetching {days}d of {interval} data...")
    current_start = start_time

    for _ in range(15):  # Limit loop count to avoid hanging
        if current_start >= end_time:
            break
        batch_end = min(current_start + 1000 * interval_ms, end_time)
        df = await fetch_klines(
            symbol, interval, limit=1000,
            start_time=current_start, end_time=batch_end
        )
        if df.empty:
            break
        all_dfs.append(df)
        current_start = int(df.index[-1].timestamp() * 1000) + interval_ms
        await asyncio.sleep(0.05)

    if not all_dfs:
        return pd.DataFrame()

    result = pd.concat(all_dfs)
    result = result[~result.index.duplicated(keep="last")]
    result.sort_index(inplace=True)
    logger.success(f"[{symbol}] Fetched {len(result)} candles ({days}d {interval})")
    return result


def _klines_to_df(raw: list) -> pd.DataFrame:
    """Convert raw Binance kline list to a clean OHLCV DataFrame."""
    if not raw:
        return pd.DataFrame()

    cols = [
        "Open_Time", "Open", "High", "Low", "Close", "Volume",
        "Close_Time", "Quote_Volume", "Trades",
        "Taker_Buy_Base", "Taker_Buy_Quote", "Ignore"
    ]
    df = pd.DataFrame(raw, columns=cols)
    df["Open_Time"] = pd.to_datetime(df["Open_Time"], unit="ms", utc=True)
    df.set_index("Open_Time", inplace=True)

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = df[col].astype(float)

    return df[["Open", "High", "Low", "Close", "Volume"]]


def _interval_to_ms(interval: str) -> int:
    """Convert timeframe string to milliseconds."""
    units = {"m": 60, "h": 3600, "d": 86400}
    unit = interval[-1]
    val = int(interval[:-1])
    return val * units[unit] * 1000


# ─────────────────────────────────────────────────────────────────────────────
# WEBSOCKET CLIENT – Live Data Stream
# ─────────────────────────────────────────────────────────────────────────────

class BinanceStreamManager:
    """
    Manages WebSocket connection to Binance for up to 300+ symbols.
    Subscribes via JSON payload in chunks of 50 to avoid URI length limits.
    Fires a callback on every kline event.
    """

    def __init__(self, symbols: List[str], on_kline_close: Callable):
        self.symbols = [s.lower() for s in symbols]
        self.on_kline_close = on_kline_close
        self._ws = None
        self._running = False

    async def start(self):
        self._running = True
        ws_endpoints = [
            "wss://stream.binance.com:9443/ws",
            "wss://data-stream.binance.vision/ws",
            "wss://stream.binance.com:443/ws",
        ]
        endpoint_idx = 0

        logger.info(f"Connecting to Binance WS for {len(self.symbols)} symbols...")

        while self._running:
            url = ws_endpoints[endpoint_idx % len(ws_endpoints)]
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                    max_size=10_000_000,
                ) as ws:
                    self._ws = ws
                    logger.success(f"[OK] Binance WebSocket connected to {url}")

                    # Subscribe in batches of 50 streams
                    all_streams = [f"{s}@kline_{settings.TIMEFRAME}" for s in self.symbols]
                    chunk_size = 50
                    for i in range(0, len(all_streams), chunk_size):
                        chunk = all_streams[i : i + chunk_size]
                        sub_msg = {
                            "method": "SUBSCRIBE",
                            "params": chunk,
                            "id": i + 1,
                        }
                        await ws.send(json.dumps(sub_msg))
                        await asyncio.sleep(0.05)

                    logger.info(f"Subscribed to {len(all_streams)} kline streams successfully")

                    async for message in ws:
                        await self._handle_message(message)
            except websockets.ConnectionClosed as e:
                logger.warning(f"WS connection closed: {e}. Reconnecting in 3s...")
                endpoint_idx += 1
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"WS error: {e}. Reconnecting in 5s...")
                endpoint_idx += 1
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _handle_message(self, raw: str):
        """Parse incoming kline message and fire callback on candle close."""
        try:
            msg = json.loads(raw)
            # Handle subscription responses
            if "result" in msg and "id" in msg:
                return

            # Support both {"data": {"k": ...}} and direct {"k": ...}
            data = msg.get("data", msg)
            kline = data.get("k", {})

            if not kline:
                return

            is_closed = kline.get("x", False)
            symbol = kline.get("s", "").upper()

            candle = {
                "symbol": symbol,
                "open_time": pd.Timestamp(kline["t"], unit="ms", tz="UTC"),
                "open": float(kline["o"]),
                "high": float(kline["h"]),
                "low": float(kline["l"]),
                "close": float(kline["c"]),
                "volume": float(kline["v"]),
                "is_closed": is_closed,
            }

            await self.on_kline_close(candle)

        except Exception as e:
            logger.error(f"Error parsing WS message: {e}")


async def get_ticker_price(symbol: str) -> float:
    """Fetch current price for a symbol using multiple endpoint fallbacks."""
    for base_url in BINANCE_REST_ENDPOINTS:
        url = f"{base_url}/api/v3/ticker/price"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(url, params={"symbol": symbol.upper()}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return float(data["price"])
        except Exception:
            continue

    # Fallback default prices if REST API is completely unreachable
    defaults = {
        "BTCUSDT": 62000.0, "ETHUSDT": 3400.0, "SOLUSDT": 145.0,
        "BNBUSDT": 570.0, "XRPUSDT": 0.58, "DOGEUSDT": 0.12,
        "ADAUSDT": 0.38, "AVAXUSDT": 24.0, "DOTUSDT": 4.5,
    }
    return defaults.get(symbol.upper(), 10.0)
