"""
Order Manager.
Handles trade execution and live SL/TP/liquidation checks on every price tick.
"""

from typing import List, Optional
from loguru import logger

from config import settings
from core.portfolio import portfolio, Position


class OrderManager:
    """
    Processes incoming price ticks and:
    - Checks all open positions for SL / TP / liquidation hits
    - Opens new paper trades on valid signals
    """

    async def on_price_tick(self, symbol: str, current_price: float, is_closed: bool):
        """
        Called on every price update for a symbol.
        Checks all open positions for exits.
        """
        positions_for_symbol = portfolio.get_positions_by_symbol(symbol)

        for pos in positions_for_symbol:
            # Update P&L and breakeven
            portfolio.update_position(pos.id, current_price)

            # Check liquidation first (hardest stop)
            if self._check_liquidation(pos, current_price):
                portfolio.close_position(pos.id, current_price, "LIQUIDATED")
                continue

            # Check Stop Loss
            if self._check_sl(pos, current_price):
                portfolio.close_position(pos.id, pos.sl_price, "LOSS")
                continue

            # Check Take Profit
            if self._check_tp(pos, current_price):
                portfolio.close_position(pos.id, pos.tp_price, "WIN")
                continue

            # Check max bars (close if exceeded)
            if is_closed and pos.bars_open >= settings.MAX_BARS_LOOKFORWARD:
                outcome = "WIN" if pos.unrealized_pnl > 0 else "LOSS"
                portfolio.close_position(pos.id, current_price, f"MAX_BARS_{outcome}")
                continue

    def open_trade(
        self,
        symbol: str,
        direction: int,
        entry_price: float,
        atr: float,
        df_slice,
        leverage: int = None,
        win_probability: float = 0.0,
    ) -> Optional[Position]:
        """
        Open a new trade using ATR-based SL and 1:2 RR TP.

        Args:
            symbol: Trading pair
            direction: 1 (long) or -1 (short)
            entry_price: Current close price
            atr: Current ATR value
            df_slice: Last N rows of OHLCV for SL calculation
            leverage: Leverage multiplier
            win_probability: ML model confidence
        """
        # SL based on recent high/low
        lookback = df_slice.tail(settings.SL_LOOKBACK)

        if direction == 1:
            sl_price = lookback["Low"].min()
            risk = entry_price - sl_price
            tp_price = entry_price + (risk * settings.RR_RATIO)
        else:
            sl_price = lookback["High"].max()
            risk = sl_price - entry_price
            tp_price = entry_price - (risk * settings.RR_RATIO)

        # Safety: SL must be meaningful (at least 0.1% from entry)
        min_risk = entry_price * 0.001
        if risk < min_risk:
            sl_price = (entry_price - min_risk) if direction == 1 else (entry_price + min_risk)
            risk = min_risk
            tp_price = entry_price + (risk * settings.RR_RATIO) if direction == 1 else entry_price - (risk * settings.RR_RATIO)

        return portfolio.open_position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            leverage=leverage or settings.DEFAULT_LEVERAGE,
            win_probability=win_probability,
        )

    def _check_liquidation(self, pos: Position, price: float) -> bool:
        if pos.direction == 1:
            return price <= pos.liquidation_price
        else:
            return price >= pos.liquidation_price

    def _check_sl(self, pos: Position, price: float) -> bool:
        if pos.direction == 1:
            return price <= pos.sl_price
        else:
            return price >= pos.sl_price

    def _check_tp(self, pos: Position, price: float) -> bool:
        if pos.direction == 1:
            return price >= pos.tp_price
        else:
            return price <= pos.tp_price


# Global order manager singleton
order_manager = OrderManager()

