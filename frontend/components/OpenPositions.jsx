/**
 * OpenPositions — Premium trading terminal: live positions with real-time P&L
 * and manual force-close capability.
 */
import { useMemo, useState } from 'react';

/**
 * bars_open is in 1-MINUTE bars.
 * < 60 bars = show minutes, >= 60 = hours+min, >= 1440 = days
 */
function formatDuration(bars) {
  if (!bars || bars < 1) return '< 1m';
  if (bars < 60) return `${bars}m`;
  if (bars < 1440) {
    const h = Math.floor(bars / 60);
    const m = bars % 60;
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  const d = Math.floor(bars / 1440);
  const h = Math.floor((bars % 1440) / 60);
  return h > 0 ? `${d}d ${h}h` : `${d}d`;
}

function formatPrice(price) {
  if (!price && price !== 0) return '--';
  if (price >= 1000) return price.toFixed(2);
  if (price >= 1) return price.toFixed(4);
  return price.toFixed(6);
}

export default function OpenPositions({ positions = [], ticks = {}, onForceClose }) {
  const [closingId, setClosingId] = useState(null);
  const [confirmId, setConfirmId] = useState(null);

  const enriched = useMemo(() => positions.map(pos => {
    const currentPrice = ticks[pos.symbol]?.price ?? pos.current_price ?? pos.entry_price;
    let unrealizedPnl = 0;
    if (pos.direction === 1) {
      unrealizedPnl = (currentPrice - pos.entry_price) * pos.quantity;
    } else {
      unrealizedPnl = (pos.entry_price - currentPrice) * pos.quantity;
    }
    const pnlPct = pos.margin_used > 0 ? (unrealizedPnl / pos.margin_used) * 100 : 0;
    const isWinning = unrealizedPnl >= 0;
    return { ...pos, livePrice: currentPrice, liveUnrealizedPnl: unrealizedPnl, livePnlPct: pnlPct, isWinning };
  }), [positions, ticks]);

  const handleCloseClick = (id) => setConfirmId(id);
  const handleCancelClose = () => setConfirmId(null);

  const handleConfirmClose = async (pos) => {
    setConfirmId(null);
    setClosingId(pos.id);
    try {
      if (onForceClose) await onForceClose(pos);
    } finally {
      setClosingId(null);
    }
  };

  const totalPnl = enriched.reduce((s, p) => s + p.liveUnrealizedPnl, 0);
  const winning = enriched.filter(p => p.isWinning).length;

  return (
    <div className="card">
      {/* Header */}
      <div className="positions-header">
        <div className="positions-title-group">
          <h2 className="card-title" style={{ marginBottom: 0 }}>Open Positions</h2>
          <div className="positions-meta">
            <span className="pos-badge pos-badge-active">{positions.length} / 20</span>
            {winning > 0 && <span className="pos-badge pos-badge-win">▲ {winning} winning</span>}
          </div>
        </div>
        <div className={`total-pnl ${totalPnl >= 0 ? 'positive' : 'negative'}`}>
          <span className="total-pnl-label">Total Unrealized P&L</span>
          <span className="total-pnl-value">
            {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
          </span>
        </div>
      </div>

      {enriched.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">◎</div>
          <div className="empty-text">No open positions</div>
          <div className="empty-sub">The bot is scanning for trade signals...</div>
        </div>
      ) : (
        <div className="positions-scroll">
          <table className="positions-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Entry</th>
                <th>Live Price</th>
                <th>SL</th>
                <th>TP</th>
                <th>Margin</th>
                <th>Unrealized P&L</th>
                <th>Duration</th>
                <th>Win%</th>
                <th>Close</th>
              </tr>
            </thead>
            <tbody>
              {enriched.map((pos) => {
                const isConfirming = confirmId === pos.id;
                const isClosing = closingId === pos.id;
                return (
                  <tr
                    key={pos.id}
                    className={`pos-row ${pos.isWinning ? 'pos-row-win' : 'pos-row-lose'} ${isClosing ? 'pos-row-closing' : ''}`}
                  >
                    {/* Symbol */}
                    <td className="col-symbol">
                      <span className="symbol-name">{pos.symbol?.replace('USDT', '')}</span>
                      <span className="symbol-suffix">/ USDT</span>
                    </td>

                    {/* Side */}
                    <td>
                      <span className={`side-badge side-${pos.direction === 1 ? 'long' : 'short'}`}>
                        {pos.direction === 1 ? '▲ LONG' : '▼ SHORT'}
                      </span>
                      <span className="leverage-tag">{pos.leverage}×</span>
                    </td>

                    {/* Entry */}
                    <td className="col-mono">{formatPrice(pos.entry_price)}</td>

                    {/* Live price */}
                    <td className={`col-mono col-live ${pos.isWinning ? 'col-live-win' : 'col-live-lose'}`}>
                      {formatPrice(pos.livePrice)}
                    </td>

                    {/* SL */}
                    <td className="col-mono col-sl">{formatPrice(pos.sl_price)}</td>

                    {/* TP */}
                    <td className="col-mono col-tp">{formatPrice(pos.tp_price)}</td>

                    {/* Margin */}
                    <td className="col-mono">${pos.margin_used?.toFixed(2)}</td>

                    {/* Unrealized P&L */}
                    <td className={`col-pnl ${pos.isWinning ? 'positive' : 'negative'}`}>
                      <span className="pnl-main">
                        {pos.liveUnrealizedPnl >= 0 ? '+' : ''}${pos.liveUnrealizedPnl.toFixed(2)}
                      </span>
                      <span className="pnl-pct">
                        ({pos.livePnlPct >= 0 ? '+' : ''}{pos.livePnlPct.toFixed(1)}%)
                      </span>
                    </td>

                    {/* Duration */}
                    <td className="col-duration">{formatDuration(pos.bars_open || 0)}</td>

                    {/* Win probability */}
                    <td className="col-winpct">
                      {pos.win_probability
                        ? <span className="win-prob-pill">{(pos.win_probability * 100).toFixed(0)}%</span>
                        : <span className="col-muted">--</span>
                      }
                    </td>

                    {/* Force close */}
                    <td className="col-close">
                      {isClosing ? (
                        <span className="close-spinner">Closing…</span>
                      ) : isConfirming ? (
                        <div className="confirm-group">
                          <button className="btn-confirm-yes" onClick={() => handleConfirmClose(pos)}>✓ Yes</button>
                          <button className="btn-confirm-no" onClick={handleCancelClose}>✕</button>
                        </div>
                      ) : (
                        <button
                          className="btn-force-close"
                          title={`Force close ${pos.symbol?.replace('USDT', '')}`}
                          onClick={() => handleCloseClick(pos.id)}
                        >
                          ✕ Close
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
