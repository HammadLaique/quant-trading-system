"""
Paper Trading Portfolio.
Tracks demo account balance, open positions, trade history, P&L.
Fully supports leveraged futures-style trading simulation.
"""

import time
import uuid
from dataclasses import dataclass, field
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
        """Convert position to JSON-serializable Python native dict."""
        return {
            "id": str(self.id),
            "symbol": str(self.symbol),
            "direction": int(self.direction),
            "entry_price": float(self.entry_price),
            "quantity": float(self.quantity),
            "margin_used": float(self.margin_used),
            "leverage": int(self.leverage),
            "sl_price": float(self.sl_price),
            "tp_price": float(self.tp_price),
            "breakeven_price": float(self.breakeven_price),
            "risk_amount": float(self.risk_amount),
            "current_price": float(self.current_price),
            "unrealized_pnl": float(self.unrealized_pnl),
            "unrealized_r": float(self.unrealized_r),
            "liquidation_price": float(self.liquidation_price),
            "sl_moved_to_be": bool(self.sl_moved_to_be),
            "open_time": float(self.open_time),
            "bars_open": int(self.bars_open),
        }


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
    pnl_r: float
    risk_amount: float
    outcome: str
    open_time: float
    close_time: float
    duration_bars: int
    win_probability: float = 0.0

    def to_dict(self) -> dict:
        """Convert closed trade to JSON-serializable Python native dict."""
        return {
            "id": str(self.id),
            "symbol": str(self.symbol),
            "direction": int(self.direction),
            "entry_price": float(self.entry_price),
            "exit_price": float(self.exit_price),
            "quantity": float(self.quantity),
            "margin_used": float(self.margin_used),
            "leverage": int(self.leverage),
            "pnl_usdt": float(self.pnl_usdt),
            "pnl_r": float(self.pnl_r),
            "risk_amount": float(self.risk_amount),
            "outcome": str(self.outcome),
            "open_time": float(self.open_time),
            "close_time": float(self.close_time),
            "duration_bars": int(self.duration_bars),
            "win_probability": float(self.win_probability),
        }


class Portfolio:
    """
    Paper trading portfolio with leverage support.
    """

    def __init__(self):
        self.balance: float = float(settings.INITIAL_BALANCE_USDT)
        self.initial_balance: float = float(settings.INITIAL_BALANCE_USDT)
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[ClosedTrade] = []
        self.equity_history: List[dict] = []
        self._record_equity()

    @property
    def total_margin_used(self) -> float:
        return float(sum(p.margin_used for p in self.positions.values()))

    @property
    def total_unrealized_pnl(self) -> float:
        return float(sum(p.unrealized_pnl for p in self.positions.values()))

    @property
    def equity(self) -> float:
        return float(self.balance + self.total_unrealized_pnl)

    @property
    def free_margin(self) -> float:
        return float(self.balance - self.total_margin_used)

    @property
    def drawdown_pct(self) -> float:
        peak = max([float(e["equity"]) for e in self.equity_history] or [self.initial_balance])
        if peak <= 0:
            return 0.0
        return float(max(0.0, (peak - self.equity) / peak * 100))

    @property
    def total_pnl(self) -> float:
        return float(self.equity - self.initial_balance)

    @property
    def total_pnl_pct(self) -> float:
        return float((self.total_pnl / self.initial_balance) * 100)

    @property
    def open_positions_count(self) -> int:
        return len(self.positions)

    @property
    def win_rate(self) -> float:
        if not self.closed_trades:
            return 0.0
        wins = sum(1 for t in self.closed_trades if t.pnl_usdt > 0)
        return float(wins / len(self.closed_trades))

    @property
    def total_r(self) -> float:
        return float(sum(t.pnl_r for t in self.closed_trades))

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
        leverage = int(leverage or settings.DEFAULT_LEVERAGE)

        open_count = self.open_positions_count
        scale_factor = 1.0 if open_count < 4 else (4.0 / (open_count + 1))
        effective_risk_pct = settings.RISK_PER_TRADE_PERCENT * scale_factor
        risk_amount = float(self.balance * (effective_risk_pct / 100))

        if direction == 1:
            risk_per_unit = float(entry_price - sl_price)
            breakeven_price = float(entry_price + risk_per_unit)
        else:
            risk_per_unit = float(sl_price - entry_price)
            breakeven_price = float(sl_price - risk_per_unit)

        if risk_per_unit <= 0:
            logger.warning(f"[{symbol}] Invalid SL: risk_per_unit={risk_per_unit:.6f}")
            return None

        quantity = float(risk_amount / risk_per_unit)
        margin_required = float((quantity * entry_price) / leverage)

        if direction == 1:
            liquidation_price = float(entry_price * (1 - 1 / leverage))
        else:
            liquidation_price = float(entry_price * (1 + 1 / leverage))

        if margin_required > self.free_margin * 0.95:
            logger.warning(f"[{symbol}] Not enough free margin. Required: ${margin_required:.2f}, Available: ${self.free_margin:.2f}")
            return None

        if self.open_positions_count >= settings.MAX_OPEN_TRADES:
            logger.warning(f"Max open trades ({settings.MAX_OPEN_TRADES}) reached.")
            return None

        if self.drawdown_pct >= settings.MAX_DRAWDOWN_PERCENT:
            logger.critical(f"[STOP] Max drawdown {settings.MAX_DRAWDOWN_PERCENT}% reached. No new trades.")
            return None

        pos = Position(
            id=str(uuid.uuid4())[:8],
            symbol=str(symbol),
            direction=int(direction),
            entry_price=float(entry_price),
            quantity=float(quantity),
            margin_used=float(margin_required),
            leverage=int(leverage),
            sl_price=float(sl_price),
            tp_price=float(tp_price),
            breakeven_price=float(breakeven_price),
            risk_amount=float(risk_amount),
            current_price=float(entry_price),
            liquidation_price=float(liquidation_price),
        )

        self.positions[pos.id] = pos
        self.balance -= margin_required

        direction_str = "LONG" if direction == 1 else "SHORT"
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
        if position_id not in self.positions:
            return None

        pos = self.positions.pop(position_id)

        if pos.direction == 1:
            price_change = float(exit_price - pos.entry_price)
        else:
            price_change = float(pos.entry_price - exit_price)

        pnl_usdt = float(price_change * pos.quantity)
        pnl_r = float(pnl_usdt / pos.risk_amount) if pos.risk_amount > 0 else 0.0

        self.balance += pos.margin_used + pnl_usdt

        trade = ClosedTrade(
            id=str(pos.id),
            symbol=str(pos.symbol),
            direction=int(pos.direction),
            entry_price=float(pos.entry_price),
            exit_price=float(exit_price),
            quantity=float(pos.quantity),
            margin_used=float(pos.margin_used),
            leverage=int(pos.leverage),
            pnl_usdt=float(pnl_usdt),
            pnl_r=float(pnl_r),
            risk_amount=float(pos.risk_amount),
            outcome=str(outcome),
            open_time=float(pos.open_time),
            close_time=float(time.time()),
            duration_bars=int(pos.bars_open),
            win_probability=float(win_probability),
        )

        self.closed_trades.append(trade)
        self._record_equity()

        tag = "[OK]" if pnl_usdt > 0 else "[FAIL]"
        logger.info(
            f"[{pos.symbol}] {tag} {outcome} | "
            f"P&L: ${pnl_usdt:+.2f} ({pnl_r:+.2f}R) | "
            f"Equity: ${self.equity:.2f}"
        )
        return trade

    def update_position(self, position_id: str, current_price: float):
        if position_id not in self.positions:
            return

        pos = self.positions[position_id]
        pos.current_price = float(current_price)
        pos.bars_open += 1

        if pos.direction == 1:
            pos.unrealized_pnl = float((current_price - pos.entry_price) * pos.quantity)
            pos.unrealized_r = float((current_price - pos.entry_price) / (pos.entry_price - pos.sl_price)) if (pos.entry_price - pos.sl_price) > 0 else 0.0
            if not pos.sl_moved_to_be and current_price >= pos.breakeven_price:
                pos.sl_price = float(pos.entry_price)
                pos.sl_moved_to_be = True
                logger.info(f"[{pos.symbol}] [LOCK] SL moved to breakeven at {pos.entry_price:.4f}")
        else:
            pos.unrealized_pnl = float((pos.entry_price - current_price) * pos.quantity)
            pos.unrealized_r = float((pos.entry_price - current_price) / (pos.sl_price - pos.entry_price)) if (pos.sl_price - pos.entry_price) > 0 else 0.0
            if not pos.sl_moved_to_be and current_price <= pos.breakeven_price:
                pos.sl_price = float(pos.entry_price)
                pos.sl_moved_to_be = True
                logger.info(f"[{pos.symbol}] [LOCK] SL moved to breakeven at {pos.entry_price:.4f}")

        self._record_equity()

    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        return [p for p in self.positions.values() if p.symbol == symbol]

    def get_stats(self) -> dict:
        wins = [t for t in self.closed_trades if t.pnl_usdt > 0]
        losses = [t for t in self.closed_trades if t.pnl_usdt <= 0]
        gross_profit = float(sum(t.pnl_usdt for t in wins))
        gross_loss = float(abs(sum(t.pnl_usdt for t in losses)))
        profit_factor = float(round(gross_profit / gross_loss, 2)) if gross_loss > 0 else 0.0

        return {
            "balance": round(float(self.balance), 2),
            "equity": round(float(self.equity), 2),
            "free_margin": round(float(self.free_margin), 2),
            "total_pnl": round(float(self.total_pnl), 2),
            "total_pnl_pct": round(float(self.total_pnl_pct), 2),
            "total_r": round(float(self.total_r), 2),
            "drawdown_pct": round(float(self.drawdown_pct), 2),
            "open_positions": int(self.open_positions_count),
            "total_trades": int(len(self.closed_trades)),
            "win_rate": round(float(self.win_rate * 100), 2),
            "profit_factor": profit_factor,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
        }

    def _record_equity(self):
        self.equity_history.append({
            "timestamp": float(time.time()),
            "equity": round(float(self.equity), 2),
            "balance": round(float(self.balance), 2),
        })
        if len(self.equity_history) > 10_000:
            self.equity_history = self.equity_history[-10_000:]


    def reset(self):
        """Reset paper money portfolio to initial balance."""
        self.balance = float(settings.INITIAL_BALANCE_USDT)
        self.initial_balance = float(settings.INITIAL_BALANCE_USDT)
        self.positions.clear()
        self.closed_trades.clear()
        self.equity_history.clear()
        self._record_equity()
        logger.info("[RESET] Portfolio reset to initial balance.")


portfolio = Portfolio()
