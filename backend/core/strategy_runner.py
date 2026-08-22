"""
Strategy Runner.
Manages all strategy instances across up to 300 trending coins.
Initializes strategies concurrently in seconds, subscribes to Binance WebSocket streams,
periodically broadcasts state to dashboard, and executes trade setups actively.
"""

import asyncio
from typing import Dict, List
from loguru import logger

from config import settings
from data.coin_universe import get_coin_universe, refresh_coin_universe
from data.binance_client import BinanceStreamManager
from strategies.ema_ml_strategy import EMAMLStrategy
from api.ws_handler import broadcast_tick, broadcast_trade_event, broadcast_portfolio


class StrategyRunner:
    """
    Central orchestrator that:
    1. Fetches top trending coins
    2. Instantly initializes strategies in parallel
    3. Starts background broadcast and market scanning loops
    4. Connects Binance WebSocket stream
    """

    INIT_BATCH_SIZE = 50

    def __init__(self):
        self.strategies: Dict[str, EMAMLStrategy] = {}
        self.stream_manager: BinanceStreamManager = None
        self.running = False
        self.initialized_count = 0

    async def start(self):
        """Main entry point. Starts all systems."""
        logger.info("[START] Starting StrategyRunner...")
        self.running = True

        # Step 1: Start background broadcast loop immediately
        asyncio.create_task(self._broadcast_loop())
        asyncio.create_task(self._trade_scanner_loop())
        asyncio.create_task(self._coin_refresh_loop())

        # Step 2: Get coin universe and pre-fetch bulk ticker prices
        from data.binance_client import fetch_all_ticker_prices
        symbols = await get_coin_universe()
        await fetch_all_ticker_prices()
        logger.info(f"Trading universe loaded: {len(symbols)} coins")

        # Step 3: Create strategy instances
        for symbol in symbols:
            self.strategies[symbol] = EMAMLStrategy(
                symbol=symbol,
                leverage=settings.DEFAULT_LEVERAGE,
            )

        # Step 4: Rapid parallel initialization (takes ~1-2 seconds total)
        await self._initialize_all_strategies(symbols)

        # Step 5: Start WebSocket stream for all coins
        active_symbols = [s for s, strat in self.strategies.items() if strat.initialized]
        logger.info(f"Starting Binance WS stream for {len(active_symbols)} active symbols")

        self.stream_manager = BinanceStreamManager(
            symbols=active_symbols,
            on_kline_close=self._on_kline,
        )

        # WebSocket stream runs forever
        await self.stream_manager.start()

    async def _initialize_all_strategies(self, symbols: List[str]):
        """Initialize strategies in fast concurrent batches."""
        total = len(symbols)
        logger.info(f"Initializing {total} strategies in parallel...")

        for i in range(0, total, self.INIT_BATCH_SIZE):
            batch = symbols[i : i + self.INIT_BATCH_SIZE]
            tasks = [self.strategies[s].initialize() for s in batch if s in self.strategies]
            await asyncio.gather(*tasks, return_exceptions=True)

            self.initialized_count = sum(
                1 for s in symbols if s in self.strategies and self.strategies[s].initialized
            )

        logger.success(f"[OK] All strategies initialized. Active: {self.initialized_count}/{total}")

    async def _on_kline(self, candle: dict):
        """Route incoming kline to the correct strategy."""
        symbol = candle.get("symbol", "")
        strategy = self.strategies.get(symbol)

        if strategy:
            await strategy.on_candle(candle)

        # Broadcast live tick to dashboard
        await broadcast_tick({
            "type": "tick",
            "symbol": symbol,
            "price": candle.get("close", 0),
            "is_closed": candle.get("is_closed", False),
        })

    async def _trade_scanner_loop(self):
        """
        Active trade scanner: runs every 5 seconds.
        Evaluates signals on buffered candles across all initialized coins
        to ensure trades are entered promptly whenever opportunities arise.
        """
        await asyncio.sleep(3)  # Brief warmup
        while self.running:
            try:
                from core.portfolio import portfolio
                # Only scan if portfolio has capacity for more trades
                if len(portfolio.positions) < settings.MAX_OPEN_TRADES:
                    for strat in list(self.strategies.values()):
                        if not strat.initialized or len(strat.buffer) < settings.EMA_SLOW + 20:
                            continue
                        # If already holding a position in this symbol, skip
                        if len(portfolio.get_positions_by_symbol(strat.symbol)) > 0:
                            continue
                        # Simulate latest candle check to trigger any pending signals
                        if strat.buffer:
                            last_c = strat.buffer[-1]
                            await strat.on_candle({
                                "symbol": strat.symbol,
                                "open_time": last_c["open_time"],
                                "open": last_c["Open"],
                                "high": last_c["High"],
                                "low": last_c["Low"],
                                "close": last_c["Close"],
                                "volume": last_c["Volume"],
                                "is_closed": True,
                            })
                        if len(portfolio.positions) >= settings.MAX_OPEN_TRADES:
                            break
            except Exception as e:
                logger.error(f"Scanner error: {e}")
            await asyncio.sleep(5)

    async def _broadcast_loop(self):
        """Periodically broadcast portfolio state to all WS clients every 2 seconds."""
        from core.portfolio import portfolio
        while self.running:
            try:
                await broadcast_portfolio({
                    "type": "portfolio",
                    **portfolio.get_stats(),
                    "equity_curve": portfolio.equity_history[-100:],
                    "open_positions": [
                        p.to_dict() for p in portfolio.positions.values()
                    ],
                    "recent_trades": [
                        t.to_dict() for t in portfolio.closed_trades[-20:]
                    ],
                    "strategy_status": [
                        s.get_status() for s in self.strategies.values()
                        if s.initialized
                    ],
                })
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
            await asyncio.sleep(2)

    async def _coin_refresh_loop(self):
        """Every 24 hours, refresh the coin universe and spin up strategies for new coins."""
        REFRESH_EVERY = 24 * 60 * 60
        while self.running:
            await asyncio.sleep(REFRESH_EVERY)
            try:
                logger.info("[Coin Refresh] 24h refresh cycle started...")
                new_coins = await refresh_coin_universe()
                added = 0
                for sym in new_coins:
                    if sym not in self.strategies:
                        strat = EMAMLStrategy(symbol=sym, leverage=settings.DEFAULT_LEVERAGE)
                        await strat.initialize()
                        if strat.initialized:
                            self.strategies[sym] = strat
                            added += 1
                if added:
                    logger.success(f"[Coin Refresh] Added {added} new coins to the universe")
            except Exception as e:
                logger.error(f"[Coin Refresh] Error during refresh: {e}")

    async def stop(self):
        self.running = False
        if self.stream_manager:
            await self.stream_manager.stop()

    def get_status(self) -> dict:
        return {
            "total_strategies": len(self.strategies),
            "initialized": self.initialized_count,
            "running": self.running,
            "symbols": list(self.strategies.keys()),
        }


# Global runner instance
runner = StrategyRunner()
