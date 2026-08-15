"""
REST API Routes.
All HTTP endpoints for the trading dashboard.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from loguru import logger

from core.portfolio import portfolio
from ml.trainer import list_trained_symbols, model_exists

router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "quant-trading-backend"}


@router.get("/portfolio")
async def get_portfolio():
    """Full portfolio stats + open positions."""
    try:
        return {
            "stats": portfolio.get_stats(),
            "open_positions": [p.to_dict() for p in portfolio.positions.values()],
        }
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return {
            "stats": portfolio.get_stats(),
            "open_positions": [],
        }


@router.get("/portfolio/equity-curve")
async def get_equity_curve(limit: int = 500):
    """Equity curve history (last N points)."""
    return {"equity_curve": portfolio.equity_history[-limit:]}


@router.get("/trades")
async def get_trades(limit: int = 50, symbol: Optional[str] = None):
    """Recent closed trades, optionally filtered by symbol."""
    trades = portfolio.closed_trades[-limit:]
    if symbol:
        trades = [t for t in trades if t.symbol == symbol.upper()]
    return {
        "total": len(portfolio.closed_trades),
        "trades": [t.to_dict() for t in reversed(trades)],
    }


@router.get("/trades/stats")
async def get_trade_stats():
    """Detailed trade statistics."""
    closed = portfolio.closed_trades
    if not closed:
        return {"message": "No trades yet"}

    wins = [t for t in closed if t.pnl_usdt > 0]
    losses = [t for t in closed if t.pnl_usdt <= 0]

    avg_win = sum(t.pnl_usdt for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.pnl_usdt for t in losses) / len(losses) if losses else 0
    avg_r_win = sum(t.pnl_r for t in wins) / len(wins) if wins else 0
    avg_r_loss = sum(t.pnl_r for t in losses) / len(losses) if losses else 0
    avg_duration = sum(t.duration_bars for t in closed) / len(closed) if closed else 0

    # Per-symbol breakdown
    symbols_seen = set(t.symbol for t in closed)
    per_symbol = {}
    for sym in symbols_seen:
        sym_trades = [t for t in closed if t.symbol == sym]
        sym_wins = [t for t in sym_trades if t.pnl_usdt > 0]
        per_symbol[sym] = {
            "total": len(sym_trades),
            "wins": len(sym_wins),
            "win_rate": round(len(sym_wins) / len(sym_trades) * 100, 1),
            "total_pnl": round(sum(t.pnl_usdt for t in sym_trades), 2),
            "total_r": round(sum(t.pnl_r for t in sym_trades), 2),
        }

    return {
        "total_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(portfolio.win_rate * 100, 2),
        "total_r": round(portfolio.total_r, 2),
        "avg_win_usdt": round(avg_win, 2),
        "avg_loss_usdt": round(avg_loss, 2),
        "avg_win_r": round(avg_r_win, 2),
        "avg_loss_r": round(avg_r_loss, 2),
        "avg_duration_bars": round(avg_duration, 1),
        "per_symbol": per_symbol,
    }


@router.get("/positions")
async def get_open_positions():
    """All currently open positions."""
    return {
        "count": len(portfolio.positions),
        "positions": [p.to_dict() for p in portfolio.positions.values()],
    }


@router.get("/strategies")
async def get_strategy_status():
    """Status of all strategy instances."""
    from core.strategy_runner import runner
    return {
        "runner": runner.get_status(),
        "trained_models": list_trained_symbols(),
    }


@router.get("/strategies/{symbol}")
async def get_symbol_strategy(symbol: str):
    """Status of a specific symbol's strategy."""
    from core.strategy_runner import runner
    symbol = symbol.upper()
    strategy = runner.strategies.get(symbol)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy not found for {symbol}")
    return strategy.get_status()


@router.get("/coins")
async def get_coins():
    """List all coins in the trading universe."""
    from data.coin_universe import get_coin_universe
    coins = await get_coin_universe()
    return {"count": len(coins), "coins": coins}


@router.post("/portfolio/reset")
async def reset_portfolio():
    """Reset the paper portfolio to initial state (emergency button)."""
    from config import settings
    portfolio.balance = settings.INITIAL_BALANCE_USDT
    portfolio.positions.clear()
    portfolio.closed_trades.clear()
    portfolio.equity_history.clear()
    portfolio._record_equity()
    logger.warning("⚠️ Portfolio reset to initial state!")
    return {"message": "Portfolio reset successfully", "balance": portfolio.balance}


@router.post("/positions/{position_id}/close")
async def force_close_position(position_id: str):
    """Force-close an open position at the current live price (manual override)."""
    from data.binance_client import get_ticker_price

    pos = portfolio.positions.get(position_id)
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")

    try:
        current_price = await get_ticker_price(pos.symbol)
    except Exception:
        current_price = pos.current_price

    trade = portfolio.close_position(
        position_id=position_id,
        exit_price=float(current_price),
        outcome="FORCE_CLOSED",
        win_probability=float(pos.win_probability if hasattr(pos, 'win_probability') else 0.0),
    )

    if trade:
        logger.info(f"[{pos.symbol}] Force-closed by user | P&L: ${trade.pnl_usdt:+.2f}")
        return {
            "message": f"Position {position_id} closed successfully",
            "symbol": pos.symbol,
            "exit_price": current_price,
            "pnl_usdt": round(trade.pnl_usdt, 2),
        }
    raise HTTPException(status_code=500, detail="Failed to close position")


