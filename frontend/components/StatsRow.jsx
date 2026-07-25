/**
 * Stats Row — 6 top-level KPI cards
 */
export default function StatsRow({ portfolio }) {
  const cards = [
    {
      label: 'Total Equity',
      value: `$${(portfolio.equity || 0).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      change: null,
      cls: portfolio.equity >= 100000 ? 'positive' : 'negative',
    },
    {
      label: 'Total P&L',
      value: `${portfolio.total_pnl >= 0 ? '+' : ''}$${(portfolio.total_pnl || 0).toFixed(2)}`,
      change: `${portfolio.total_pnl_pct >= 0 ? '+' : ''}${(portfolio.total_pnl_pct || 0).toFixed(2)}%`,
      cls: portfolio.total_pnl >= 0 ? 'positive' : 'negative',
    },
    {
      label: 'Total R-Multiple',
      value: `${portfolio.total_r >= 0 ? '+' : ''}${(portfolio.total_r || 0).toFixed(2)}R`,
      change: null,
      cls: portfolio.total_r >= 0 ? 'positive' : 'negative',
    },
    {
      label: 'Win Rate',
      value: `${(portfolio.win_rate || 0).toFixed(1)}%`,
      change: `${portfolio.total_trades || 0} trades`,
      cls: portfolio.win_rate >= 50 ? 'positive' : 'negative',
    },
    {
      label: 'Profit Factor',
      value: portfolio.profit_factor === Infinity ? '∞' : (portfolio.profit_factor || 0).toFixed(2),
      change: null,
      cls: portfolio.profit_factor >= 1.5 ? 'positive' : 'negative',
    },
    {
      label: 'Max Drawdown',
      value: `${(portfolio.drawdown_pct || 0).toFixed(2)}%`,
      change: `${portfolio.open_positions || 0} open`,
      cls: portfolio.drawdown_pct < 10 ? 'positive' : 'negative',
    },
  ];

  return (
    <div className="stats-row">
      {cards.map((card) => (
        <div key={card.label} className={`stat-card ${card.cls}`}>
          <div className="label">{card.label}</div>
          <div className="value mono">{card.value}</div>
          {card.change && (
            <div className={`change ${card.cls}`}>{card.change}</div>
          )}
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width: card.label === 'Win Rate'
                  ? `${Math.min(portfolio.win_rate || 0, 100)}%`
                  : card.label === 'Max Drawdown'
                  ? `${Math.min(portfolio.drawdown_pct || 0, 100)}%`
                  : '60%',
                background: card.cls === 'negative'
                  ? 'linear-gradient(90deg, #ff3366, #ff6600)'
                  : undefined,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
