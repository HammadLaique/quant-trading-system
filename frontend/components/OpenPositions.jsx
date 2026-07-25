/**
 * OpenPositions — Table of all active leveraged positions with live P&L
 */
import { useMemo } from 'react';

function formatDuration(bars) {
  if (bars < 60) return `${bars}m`;
  if (bars < 1440) return `${Math.floor(bars / 60)}h ${bars % 60}m`;
  return `${Math.floor(bars / 1440)}d`;
}

export default function OpenPositions({ positions = [], ticks = {} }) {
  const enriched = useMemo(() => positions.map(pos => {
    const currentPrice = ticks[pos.symbol]?.price ?? pos.current_price;
    let unrealizedPnl = 0;
    if (pos.direction === 1) {
      unrealizedPnl = (currentPrice - pos.entry_price) * pos.quantity;
    } else {
      unrealizedPnl = (pos.entry_price - currentPrice) * pos.quantity;
    }
    const pnlPct = (unrealizedPnl / pos.margin_used) * 100;
    return { ...pos, livePrice: currentPrice, liveUnrealizedPnl: unrealizedPnl, livePnlPct: pnlPct };
  }), [positions, ticks]);

  return (
    <div className="card">
      <div className="flex-between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ marginBottom: 0 }}>Open Positions</div>
        <span className="badge badge-cyan">{positions.length} active</span>
      </div>

      {enriched.length === 0 ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', padding: '20px 0' }}>
          No open positions
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Dir</th>
                <th>Leverage</th>
                <th>Entry</th>
                <th>Live Price</th>
                <th>SL</th>
                <th>TP</th>
                <th>Size</th>
                <th>Margin</th>
                <th>Unrealized P&L</th>
                <th>Duration</th>
                <th>ML Prob</th>
              </tr>
            </thead>
            <tbody>
              {enriched.map((pos) => {
                const isWinning = pos.liveUnrealizedPnl > 0;
                return (
                  <tr key={pos.id}>
                    <td style={{ fontWeight: 700 }}>{pos.symbol?.replace('USDT', '')}</td>
                    <td>
                      <span className={`badge badge-${pos.direction === 1 ? 'long' : 'short'}`}>
                        {pos.direction === 1 ? 'LONG' : 'SHORT'}
                      </span>
                    </td>
                    <td style={{ color: 'var(--accent-yellow)' }}>{pos.leverage}x</td>
                    <td>{pos.entry_price?.toFixed(4)}</td>
                    <td style={{ color: isWinning ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                      {pos.livePrice?.toFixed(4)}
                    </td>
                    <td style={{ color: 'var(--accent-red)' }}>{pos.sl_price?.toFixed(4)}</td>
                    <td style={{ color: 'var(--accent-green)' }}>{pos.tp_price?.toFixed(4)}</td>
                    <td>{pos.quantity?.toFixed(4)}</td>
                    <td>${pos.margin_used?.toFixed(2)}</td>
                    <td className={isWinning ? 'positive' : 'negative'}>
                      {isWinning ? '+' : ''}${pos.liveUnrealizedPnl?.toFixed(2)}
                      <span style={{ color: 'var(--text-muted)', marginLeft: 4, fontSize: 10 }}>
                        ({pos.livePnlPct >= 0 ? '+' : ''}{pos.livePnlPct?.toFixed(1)}%)
                      </span>
                    </td>
                    <td>{formatDuration(pos.bars_open || 0)}</td>
                    <td style={{ color: 'var(--accent-cyan)' }}>
                      {pos.win_probability ? `${(pos.win_probability * 100).toFixed(0)}%` : '--'}
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
