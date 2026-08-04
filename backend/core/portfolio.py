"""
Paper Trading Portfolio.
Tracks demo account balance, open positions, trade history, P&L.
Fully supports leveraged futures-style trading simulation.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from loguru import logger
from config import settings


@dataclass
class Position:
    """Represents a single open leveraged position."""
    id: str
    symbol: str
    direction: int           # 1 = LONG, -1 = SHORT
    entry_price: float
    quantity: float          # in base asset (e.g., BTC amount)
    margin_used: float       # USDT allocated as margin
    leverage: int
    sl_price: float
    tp_price: float
    breakeven_price: float   # price at which SL moves to entry
    risk_amount: float       # USDT at risk (1R)
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_r: float = 0.0
    liquidation_price: float = 0.0
    sl_moved_to_be: bool = False
    open_time: float = field(default_factory=time.time)
    bars_open: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClosedTrade:
    """Record of a completed trade."""
    id: str
    symbol: str
    direction: int
    entry_price: float
    exit_price: float
    quantity: float
    margin_used: float
    leverage: int
    pnl_usdt: float
    pnl_r: float             # profit in R-multiples
    risk_amount: float
    outcome: str             # 'WIN' | 'LOSS' | 'LIQUIDATED' | 'MAX_BARS'
    open_time: float
    close_time: float
    duration_bars: int
    win_probability: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class Portfolio:
    """
    Paper trading portfolio with leverage support.
    """

    def __init__(self):
        self.balance: float = settings.INITIAL_BALANCE_USDT
        self.initial_balance: float = settings.INITIAL_BALANCE_USDT
        self.positions: Dict[str, Position] = {}   # position_id → Position
        self.closed_trades: List[ClosedTrade] = []
        self.equity_history: List[dict] = []
        self._record_equity()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def total_margin_used(self) -> float:
        return sum(p.margin_used for p in self.positions.values())

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def equity(self) -> float:
        return self.balance + self.total_unrealized_pnl

    @property
    def free_margin(self) -> float:
        return self.balance - self.total_margin_used

    @property
    def drawdown_pct(self) -> float:
        peak = max([e["equity"] for e in self.equity_history] or [self.initial_balance])
        if peak == 0:
            return 0.0
        return max(0.0, (peak - self.equity) / peak * 100)

    @property
    def total_pnl(self) -> float:
        return self.equity - self.initial_balance

    @property
    def total_pnl_pct(self) -> float:
        return (self.total_pnl / self.initial_balance) * 100

    @property
    def open_positions_count(self) -> int:
        return len(self.positions)

    @property
    def win_rate(self) -> float:
        if not self.closed_trades:
            return 0.0
        wins = sum(1 for t in self.closed_trades if t.pnl_usdt > 0)
        return wins / len(self.closed_trades)

    @property
    def total_r(self) -> float:
        return sum(t.pnl_r for t in self.closed_trades)

    # ── Position Management ───────────────────────────────────────────────

    def open_position(
        self,
        symbol: str,
        direction: int,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        leverage: int = None,
        win_probability: float = 0.0,
    ) -> Optional[Position]:
        """
        Open a new leveraged paper position.
        Returns the Position object, or None if not enough margin.
        """
        leverage = leverage or settings.DEFAULT_LEVERAGE

        # Dynamic risk scaling: base risk is 1.0%, but as open positions increase (up to 10),
        # position margin scales down proportionately so total wallet risk stays safe at 100x leverage
        open_count = self.open_positions_count
        scale_factor = 1.0 if open_count < 4 else (4.0 / (open_count + 1))
        effective_risk_pct = settings.RISK_PER_TRADE_PERCENT * scale_factor
        risk_amount = self.balance * (effective_risk_pct / 100)

        if direction == 1:  # Long
            risk_per_unit = entry_price - sl_price
            breakeven_price = entry_price + risk_per_unit
        else:  # Short
            risk_per_unit = sl_price - entry_price
            breakeven_price = entry_price - risk_per_unit

        if risk_per_unit <= 0:
            logger.warning(f"[{symbol}] Invalid SL: risk_per_unit={risk_per_unit:.6f}")
            return None

        # Quantity = how many units to buy given risk
        quantity = risk_amount / risk_per_unit
        margin_required = (quantity * entry_price) / leverage

        # Liquidation price (for longs: entry / (1 + 1/leverage))
        if direction == 1:
            liquidation_price = entry_price * (1 - 1 / leverage)
        else:
            liquidation_price = entry_price * (1 + 1 / leverage)

        # Check if we have enough free margin
        if margin_required > self.free_margin * 0.95:
            logger.warning(f"[{symbol}] Not enough free margin. Required: ${margin_required:.2f}, Available: ${self.free_margin:.2f}")
            return None

        # Check max open trades
        if self.open_positions_count >= settings.MAX_OPEN_TRADES:
            logger.warning(f"Max open trades ({settings.MAX_OPEN_TRADES}) reached.")
            return None

        # Check max drawdown guard
        if self.drawdown_pct >= settings.MAX_DRAWDOWN_PERCENT:
            logger.critical(f"[STOP] Max drawdown {settings.MAX_DRAWDOWN_PERCENT}% reached. No new trades.")
            return None

        pos = Position(
            id=str(uuid.uuid4())[:8],
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            margin_used=margin_required,
            leverage=leverage,
            sl_price=sl_price,
            tp_price=tp_price,
            breakeven_price=breakeven_price,
            risk_amount=risk_amount,
            current_price=entry_price,
            liquidation_price=liquidation_price,
        )

        self.positions[pos.id] = pos
        self.balance -= margin_required  # Reserve margin

        direction_str = "LONG [LONG]" if direction == 1 else "SHORT [SHORT]"
        logger.info(
            f"[{symbol}] {direction_str} opened | "
            f"Entry: {entry_price:.4f} | SL: {sl_price:.4f} | TP: {tp_price:.4f} | "
            f"Size: {quantity:.4f} | Leverage: {leverage}x | Margin: ${margin_required:.2f}"
        )
        return pos

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        outcome: str,
        win_probability: float = 0.0,
    ) -> Optional[ClosedTrade]:
        """Close an open position and record the trade."""
        if position_id not in self.positions:
            return None

        pos = self.positions.pop(position_id)

        # Calculate P&L
        if pos.direction == 1:
            price_change = exit_price - pos.entry_price
        else:
            price_change = pos.entry_price - exit_price

        pnl_usdt = price_change * pos.quantity
        pnl_r = pnl_usdt / pos.risk_amount if pos.risk_amount > 0 else 0.0

        # Return margin + profit to balance
        self.balance += pos.margin_used + pnl_usdt

        trade = ClosedTrade(
            id=pos.id,
            symbol=pos.symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            quantity=pos.quantity,
            margin_used=pos.margin_used,
            leverage=pos.leverage,
            pnl_usdt=pnl_usdt,
            pnl_r=pnl_r,
            risk_amount=pos.risk_amount,
            outcome=outcome,
            open_time=pos.open_time,
            close_time=time.time(),
            duration_bars=pos.bars_open,
            win_probability=win_probability,
        )

        self.closed_trades.append(trade)
        self._record_equity()

        emoji = "[OK]" if pnl_usdt > 0 else "[FAIL]"
        logger.info(
            f"[{pos.symbol}] {emoji} {outcome} | "
            f"P&L: ${pnl_usdt:+.2f} ({pnl_r:+.2f}R) | "
            f"Equity: ${self.equity:.2f}"
        )
        return trade

    def update_position(self, position_id: str, current_price: float):
        """Update unrealized P&L and check breakeven condition."""
        if position_id not in self.positions:
            return

        pos = self.positions[position_id]
        pos.current_price = current_price
        pos.bars_open += 1

        if pos.direction == 1:
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.quantity
            pos.unrealized_r = (current_price - pos.entry_price) / (pos.entry_price - pos.sl_price) if (pos.entry_price - pos.sl_price) > 0 else 0
            # Move SL to breakeven when 1R profit reached
            if not pos.sl_moved_to_be and current_price >= pos.breakeven_price:
                pos.sl_price = pos.entry_price
                pos.sl_moved_to_be = True
                logger.info(f"[{pos.symbol}] [LOCK] SL moved to breakeven at {pos.entry_price:.4f}")
        else:
            pos.unrealized_pnl = (pos.entry_price - current_price) * pos.quantity
            pos.unrealized_r = (pos.entry_price - current_price) / (pos.sl_price - pos.entry_price) if (pos.sl_price - pos.entry_price) > 0 else 0
            if not pos.sl_moved_to_be and current_price <= pos.breakeven_price:
                pos.sl_price = pos.entry_price
                pos.sl_moved_to_be = True
                logger.info(f"[{pos.symbol}] [LOCK] SL moved to breakeven at {pos.entry_price:.4f}")

        self._record_equity()

    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        return [p for p in self.positions.values() if p.symbol == symbol]

    def get_stats(self) -> dict:
        """Return comprehensive portfolio statistics."""
        wins = [t for t in self.closed_trades if t.pnl_usdt > 0]
        losses = [t for t in self.closed_trades if t.pnl_usdt <= 0]
        gross_profit = sum(t.pnl_usdt for t in wins)
        gross_loss = abs(sum(t.pnl_usdt for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        return {
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "free_margin": round(self.free_margin, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "total_r": round(self.total_r, 2),
            "drawdown_pct": round(self.drawdown_pct, 2),
            "open_positions": self.open_positions_count,
            "total_trades": len(self.closed_trades),
            "win_rate": round(self.win_rate * 100, 2),
            "profit_factor": round(profit_factor, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
        }

    def _record_equity(self):
        self.equity_history.append({
            "timestamp": time.time(),
            "equity": round(self.equity, 2),
            "balance": round(self.balance, 2),
        })
        # Keep last 10,000 equity points
        if len(self.equity_history) > 10_000:
            self.equity_history = self.equity_history[-10_000:]


# Global portfolio singleton
portfolio = Portfolio()

