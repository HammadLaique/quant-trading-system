"""
Strategy Runner.
Manages all strategy instances across 100 coins.
Initializes strategies in batches, subscribes to Binance WebSocket streams,
and routes incoming candle data to the correct strategy.
"""

import asyncio
from typing import Dict, List
from loguru import logger

from config import settings
from data.coin_universe import get_coin_universe
from data.binance_client import BinanceStreamManager
from strategies.ema_ml_strategy import EMAMLStrategy
from api.ws_handler import broadcast_tick, broadcast_trade_event, broadcast_portfolio


class StrategyRunner:
    """
    Central orchestrator that:
    1. Fetches top 100 coins
    2. Creates per-coin strategy instances
    3. Initializes strategies in parallel batches (avoid rate limits)
    4. Starts Binance WebSocket and routes candles to strategies
    5. Periodically broadcasts state to connected WebSocket clients
    """

    INIT_BATCH_SIZE = 5    # Initialize N strategies at a time
    INIT_BATCH_DELAY = 2   # Seconds between batches (rate limit)

    def __init__(self):
        self.strategies: Dict[str, EMAMLStrategy] = {}
        self.stream_manager: BinanceStreamManager = None
        self.running = False
        self.initialized_count = 0

    async def start(self):
        """Main entry point. Starts everything."""
        logger.info("[START] Starting StrategyRunner...")
        self.running = True

        # Step 1: Get coin universe
        symbols = await get_coin_universe()
        logger.info(f"Trading universe: {len(symbols)} coins")

        # Step 2: Create strategy instances
        for symbol in symbols:
            self.strategies[symbol] = EMAMLStrategy(
                symbol=symbol,
                leverage=settings.DEFAULT_LEVERAGE,
            )

        # Step 3: Initialize strategies in batches
        await self._initialize_all_strategies(symbols)

        # Step 4: Start WebSocket stream for all coins
        active_symbols = [s for s, strat in self.strategies.items() if strat.initialized]
        logger.info(f"Starting WS stream for {len(active_symbols)} initialized strategies")

        self.stream_manager = BinanceStreamManager(
            symbols=active_symbols,
            on_kline_close=self._on_kline,
        )

        # Step 5: Start background broadcasting task
        asyncio.create_task(self._broadcast_loop())

        # Step 6: Start WebSocket (runs forever)
        await self.stream_manager.start()

    async def _initialize_all_strategies(self, symbols: List[str]):
        """Initialize strategies in batches to respect rate limits."""
        total = len(symbols)
        logger.info(f"Initializing {total} strategies in batches of {self.INIT_BATCH_SIZE}...")

        for i in range(0, total, self.INIT_BATCH_SIZE):
            batch = symbols[i: i + self.INIT_BATCH_SIZE]
            tasks = [self.strategies[s].initialize() for s in batch]
            await asyncio.gather(*tasks, return_exceptions=True)

            self.initialized_count = sum(
                1 for s in symbols if self.strategies[s].initialized
            )

            progress = min(i + self.INIT_BATCH_SIZE, total)
            logger.info(f"Initialized {progress}/{total} strategies...")

            if i + self.INIT_BATCH_SIZE < total:
                await asyncio.sleep(self.INIT_BATCH_DELAY)

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

    async def _broadcast_loop(self):
        """Periodically broadcast portfolio state to all WS clients."""
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
            await asyncio.sleep(2)  # Broadcast every 2 seconds

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

