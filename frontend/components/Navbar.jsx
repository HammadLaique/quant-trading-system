/**
 * Navbar — sticky header with live portfolio stats and connection indicator
 */
export default function Navbar({ portfolio, connected }) {
  const pnlColor = portfolio.total_pnl >= 0 ? '#00ff88' : '#ff3366';

  return (
    <nav className="navbar">
      <a className="navbar-brand" href="/">
        <span className="logo-dot" />
        QuantBot <span style={{ color: 'var(--accent-cyan)', marginLeft: 4 }}>Pro</span>
      </a>

      <div className="navbar-stats">
        <div className="navbar-stat">
          <span>Equity</span>
          <strong style={{ fontFamily: 'var(--font-mono)' }}>
            ${portfolio.equity?.toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </strong>
        </div>
        <div className="navbar-stat">
          <span>P&L</span>
          <strong style={{ color: pnlColor, fontFamily: 'var(--font-mono)' }}>
            {portfolio.total_pnl >= 0 ? '+' : ''}${portfolio.total_pnl?.toFixed(2)}
          </strong>
        </div>
        <div className="navbar-stat">
          <span>Win Rate</span>
          <strong style={{ fontFamily: 'var(--font-mono)' }}>{portfolio.win_rate?.toFixed(1)}%</strong>
        </div>
        <div className="navbar-stat">
          <span>Total R</span>
          <strong style={{ color: portfolio.total_r >= 0 ? '#00ff88' : '#ff3366', fontFamily: 'var(--font-mono)' }}>
            {portfolio.total_r >= 0 ? '+' : ''}{portfolio.total_r?.toFixed(1)}R
          </strong>
        </div>

        {connected ? (
          <div className="live-badge">Live</div>
        ) : (
          <div className="live-badge" style={{ borderColor: 'rgba(255,51,102,0.3)', background: 'rgba(255,51,102,0.1)', color: '#ff3366' }}>
            Reconnecting...
          </div>
        )}
      </div>
    </nav>
  );
}
