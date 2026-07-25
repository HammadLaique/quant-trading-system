/**
 * CoinGrid — Grid of all 100 coins showing live prices and status
 * Color-coded: green = long position, red = short, yellow = signal, default = monitoring
 */
import { useMemo } from 'react';

function CoinTile({ symbol, tick, positions, strategies }) {
  const baseName = symbol.replace('USDT', '');
  const price = tick?.price;
  const symbolPositions = positions.filter(p => p.symbol === symbol);
  const hasLong = symbolPositions.some(p => p.direction === 1);
  const hasShort = symbolPositions.some(p => p.direction === -1);

  const strat = strategies.find(s => s.symbol === symbol);
  const hasSignal = strat?.last_signal !== 0;

  let tileClass = 'coin-tile';
  if (hasLong) tileClass += ' has-position-long';
  else if (hasShort) tileClass += ' has-position-short';
  else if (hasSignal) tileClass += ' has-signal';

  return (
    <div className={tileClass} title={symbol}>
      <div className="coin-name">{baseName}</div>
      {price ? (
        <div className="coin-price">${formatPrice(price)}</div>
      ) : (
        <div className="coin-price" style={{ color: 'var(--text-muted)' }}>Loading...</div>
      )}
      {symbolPositions.length > 0 && (
        <div className={`coin-change ${hasLong ? 'positive' : 'negative'}`}>
          {hasLong ? '▲ LONG' : '▼ SHORT'}
        </div>
      )}
      {strat && !symbolPositions.length && (
        <div style={{ marginTop: 2, height: 3, borderRadius: 2, background: 'var(--bg-elevated)' }}>
          <div style={{
            width: strat.model_ready ? '80%' : '0%',
            height: '100%',
            background: 'var(--accent-cyan)',
            borderRadius: 2,
            opacity: 0.5,
          }} />
        </div>
      )}
    </div>
  );
}

function formatPrice(price) {
  if (price >= 1000) return price.toLocaleString('en', { maximumFractionDigits: 2 });
  if (price >= 1) return price.toFixed(4);
  return price.toFixed(6);
}

export default function CoinGrid({ coins = [], ticks = {}, positions = [], strategies = [] }) {
  return (
    <div className="card">
      <div className="flex-between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ marginBottom: 0 }}>
          Coin Universe
        </div>
        <div style={{ display: 'flex', gap: 10, fontSize: 10, color: 'var(--text-muted)' }}>
          <span>🟢 Long</span>
          <span>🔴 Short</span>
          <span>🟡 Signal</span>
          <span style={{ color: 'var(--text-secondary)' }}>{coins.length} coins</span>
        </div>
      </div>
      <div className="coin-grid">
        {coins.map(symbol => (
          <CoinTile
            key={symbol}
            symbol={symbol}
            tick={ticks[symbol]}
            positions={positions}
            strategies={strategies}
          />
        ))}
        {coins.length === 0 && (
          <div style={{
            gridColumn: '1/-1', textAlign: 'center',
            color: 'var(--text-muted)', padding: '40px 0', fontSize: 13
          }}>
            Loading coin universe...
          </div>
        )}
      </div>
    </div>
  );
}
