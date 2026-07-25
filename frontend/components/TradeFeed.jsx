/**
 * TradeFeed — Live scrolling list of recent trades with animated entry
 */
import { useMemo } from 'react';

function formatTime(timestamp) {
  if (!timestamp) return '--';
  return new Date(timestamp * 1000).toLocaleTimeString();
}

function TradeRow({ trade }) {
  const isWin = trade.pnl_usdt > 0;
  const dirLabel = trade.direction === 1 ? 'LONG' : 'SHORT';

  return (
    <div className="trade-item">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span className="trade-symbol">{trade.symbol?.replace('USDT', '')}</span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{formatTime(trade.close_time)}</span>
      </div>

      <span className={`badge badge-${trade.direction === 1 ? 'long' : 'short'}`}>
        {dirLabel}
      </span>

      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' }}>
        {trade.leverage}x
      </span>

      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', marginLeft: 'auto' }}>
        {trade.pnl_r >= 0 ? '+' : ''}{trade.pnl_r?.toFixed(2)}R
      </span>

      <span className={`trade-pnl ${isWin ? 'positive' : 'negative'}`}>
        {isWin ? '+' : ''}${trade.pnl_usdt?.toFixed(2)}
      </span>

      <span className={`badge badge-${isWin ? 'win' : 'loss'}`}>
        {trade.outcome?.includes('WIN') ? 'WIN' : 'LOSS'}
      </span>
    </div>
  );
}

export default function TradeFeed({ trades = [] }) {
  const displayTrades = useMemo(() => trades.slice(0, 25), [trades]);

  return (
    <div className="card" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="flex-between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ marginBottom: 0 }}>Trade Feed</div>
        <span className="badge badge-cyan">{trades.length} total</span>
      </div>

      {displayTrades.length === 0 ? (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text-muted)', fontSize: 13, flexDirection: 'column', gap: 8
        }}>
          <span style={{ fontSize: 24 }}>⏳</span>
          <span>Waiting for first trade...</span>
          <span style={{ fontSize: 11 }}>Strategy is initializing models</span>
        </div>
      ) : (
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {displayTrades.map((trade, i) => (
            <TradeRow key={`${trade.id}-${i}`} trade={trade} />
          ))}
        </div>
      )}
    </div>
  );
}
