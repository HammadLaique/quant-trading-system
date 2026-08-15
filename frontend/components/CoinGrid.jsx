/**
 * CoinGrid — Grid of all trending coins showing live prices and status
 * Color-coded: green = long position, red = short, yellow = real active signal, default = monitoring
 */
import { useMemo } from 'react';

function CoinTile({ symbol, tick, positions, strategies }) {
  const baseName = symbol.replace('USDT', '');
  const price = tick?.price;
  const symbolPositions = positions.filter(p => p.symbol === symbol);
  const hasLong = symbolPositions.some(p => p.direction === 1);
  const hasShort = symbolPositions.some(p => p.direction === -1);

  // Fix: Only true if strategy actually exists and signal is 1 or -1
  const strat = strategies.find(s => s.symbol === symbol);
  const hasSignal = !!strat && strat.last_signal !== 0 && strat.last_signal !== undefined && strat.last_signal !== null;

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
        <div className="coin-price" style={{ color: 'var(--text-muted)' }}>--</div>
      )}
      {symbolPositions.length > 0 ? (
        <div className={`coin-change ${hasLong ? 'positive' : 'negative'}`}>
          {hasLong ? '▲ LONG' : '▼ SHORT'}
        </div>
      ) : hasSignal ? (
        <div className="coin-change" style={{ color: 'var(--accent-yellow)' }}>
          ⚡ {strat.last_signal === 1 ? 'BUY' : 'SELL'}
        </div>
      ) : (
        strat && (
          <div style={{ marginTop: 4, height: 2, borderRadius: 1, background: 'var(--bg-elevated)' }}>
            <div style={{
              width: strat.model_ready ? '100%' : '50%',
              height: '100%',
              background: strat.model_ready ? 'var(--accent-green)' : 'var(--accent-cyan)',
              borderRadius: 1,
              opacity: 0.6,
            }} />
          </div>
        )
      )}
    </div>
  );
}

function formatPrice(price) {
  if (!price && price !== 0) return '--';
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (isNaN(num)) return '--';
  if (num >= 1000) return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (num >= 1) return num.toFixed(4);
  return num.toFixed(6);
}

export default function CoinGrid({ coins = [], ticks = {}, positions = [], strategies = [] }) {
  return (
    <div className="card">
      <div className="flex-between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ marginBottom: 0 }}>
          Coin Universe
        </div>
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ color: 'var(--accent-green)' }}>● Long</span>
          <span style={{ color: 'var(--accent-red)' }}>● Short</span>
          <span style={{ color: 'var(--accent-yellow)' }}>● Signal</span>
          <span style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>{coins.length} coins</span>
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
