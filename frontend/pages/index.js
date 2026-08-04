/**
 * Main Dashboard Page
 * Real-time autonomous trading bot dashboard
 */
import Head from 'next/head';
import { useEffect, useState } from 'react';
import { useTradingSocket } from '../hooks/useTradingSocket';
import Navbar from '../components/Navbar';
import StatsRow from '../components/StatsRow';
import EquityChart from '../components/EquityChart';
import TradeFeed from '../components/TradeFeed';
import OpenPositions from '../components/OpenPositions';
import CoinGrid from '../components/CoinGrid';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://quant-trading-system-0nf9.onrender.com/api';

export default function Dashboard() {
  const { connected, portfolio, ticks, tradeEvents } = useTradingSocket();
  const [coins, setCoins] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');

  // Fetch coin universe once
  useEffect(() => {
    fetch(`${API_URL}/coins`)
      .then(r => r.json())
      .then(data => setCoins(data.coins || []))
      .catch(() => {});
  }, []);

  return (
    <>
      <Head>
        <title>QuantBot Pro — Autonomous Crypto Trading</title>
        <meta name="description" content="Real-time autonomous cryptocurrency trading bot dashboard with ML-powered signals across top 100 coins" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="layout">
        <Navbar portfolio={portfolio} connected={connected} />

        <main className="main-content">
          {/* KPI Stats Row */}
          <StatsRow portfolio={portfolio} />

          {/* Tab Navigation */}
          <div style={{
            display: 'flex', gap: 4,
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: 4,
            marginTop: 20,
            width: 'fit-content',
          }}>
            {['overview', 'positions', 'coins', 'trades'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  background: activeTab === tab ? 'var(--accent-cyan-dim)' : 'transparent',
                  border: activeTab === tab ? '1px solid var(--border-bright)' : '1px solid transparent',
                  color: activeTab === tab ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  padding: '6px 18px',
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  textTransform: 'capitalize',
                }}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16, marginTop: 16 }}>
              {/* Left column */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <EquityChart equityCurve={portfolio.equity_curve} />
                <OpenPositions
                  positions={portfolio.open_positions_list || []}
                  ticks={ticks}
                />
              </div>

              {/* Right column */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <TradeFeed trades={portfolio.recent_trades || []} />
                <StrategyStatus strategies={portfolio.strategy_status || []} />
              </div>
            </div>
          )}

          {/* Positions Tab */}
          {activeTab === 'positions' && (
            <div style={{ marginTop: 16 }}>
              <OpenPositions
                positions={portfolio.open_positions_list || []}
                ticks={ticks}
              />
            </div>
          )}

          {/* Coins Tab */}
          {activeTab === 'coins' && (
            <div style={{ marginTop: 16 }}>
              <CoinGrid
                coins={coins}
                ticks={ticks}
                positions={portfolio.open_positions_list || []}
                strategies={portfolio.strategy_status || []}
              />
            </div>
          )}

          {/* Trades Tab */}
          {activeTab === 'trades' && (
            <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16 }}>
              <AllTradesTable trades={portfolio.recent_trades || []} />
              <TradeStatsPanel portfolio={portfolio} />
            </div>
          )}
        </main>

        <Footer />
      </div>
    </>
  );
}

// ── Strategy Status Panel ────────────────────────────────────────────────────
function StrategyStatus({ strategies }) {
  const initialized = strategies.filter(s => s.initialized).length;
  const modelReady = strategies.filter(s => s.model_ready).length;

  return (
    <div className="card">
      <div className="flex-between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ marginBottom: 0 }}>Strategy Status</div>
        <span className="badge badge-cyan">{initialized} active</span>
      </div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>INITIALIZED</div>
          <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
            {initialized}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>MODELS READY</div>
          <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--accent-green)' }}>
            {modelReady}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>TOTAL COINS</div>
          <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
            {strategies.length}
          </div>
        </div>
      </div>
      <div style={{ height: 6, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${strategies.length ? (initialized / strategies.length) * 100 : 0}%`,
          background: 'linear-gradient(90deg, var(--accent-cyan), var(--accent-green))',
          borderRadius: 3,
          transition: 'width 1s ease',
        }} />
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6 }}>
        Initialization progress
      </div>
    </div>
  );
}

// ── All Trades Table ─────────────────────────────────────────────────────────
function AllTradesTable({ trades }) {
  return (
    <div className="card">
      <div className="card-title">All Trades</div>
      <div style={{ overflowX: 'auto', maxHeight: 600, overflowY: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Dir</th>
              <th>Lev</th>
              <th>Entry</th>
              <th>Exit</th>
              <th>P&L USDT</th>
              <th>P&L R</th>
              <th>Outcome</th>
              <th>ML%</th>
            </tr>
          </thead>
          <tbody>
            {[...trades].reverse().map((t, i) => (
              <tr key={`${t.id}-${i}`}>
                <td style={{ fontWeight: 700 }}>{t.symbol?.replace('USDT', '')}</td>
                <td>
                  <span className={`badge badge-${t.direction === 1 ? 'long' : 'short'}`}>
                    {t.direction === 1 ? 'L' : 'S'}
                  </span>
                </td>
                <td style={{ color: 'var(--accent-yellow)' }}>{t.leverage}x</td>
                <td>{t.entry_price?.toFixed(4)}</td>
                <td>{t.exit_price?.toFixed(4)}</td>
                <td className={t.pnl_usdt >= 0 ? 'positive' : 'negative'}>
                  {t.pnl_usdt >= 0 ? '+' : ''}${t.pnl_usdt?.toFixed(2)}
                </td>
                <td className={t.pnl_r >= 0 ? 'positive' : 'negative'}>
                  {t.pnl_r >= 0 ? '+' : ''}{t.pnl_r?.toFixed(2)}R
                </td>
                <td>
                  <span className={`badge badge-${t.pnl_usdt >= 0 ? 'win' : 'loss'}`}>
                    {t.outcome?.includes('WIN') ? 'WIN' : 'LOSS'}
                  </span>
                </td>
                <td style={{ color: 'var(--accent-cyan)' }}>
                  {t.win_probability ? `${(t.win_probability * 100).toFixed(0)}%` : '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Trade Stats Panel ────────────────────────────────────────────────────────
function TradeStatsPanel({ portfolio }) {
  const items = [
    { label: 'Total Trades', value: portfolio.total_trades || 0, color: 'var(--text-primary)' },
    { label: 'Win Rate', value: `${(portfolio.win_rate || 0).toFixed(1)}%`, color: portfolio.win_rate >= 50 ? 'var(--accent-green)' : 'var(--accent-red)' },
    { label: 'Total R', value: `${(portfolio.total_r || 0) >= 0 ? '+' : ''}${(portfolio.total_r || 0).toFixed(2)}R`, color: portfolio.total_r >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' },
    { label: 'Profit Factor', value: portfolio.profit_factor === Infinity ? '∞' : (portfolio.profit_factor || 0).toFixed(2), color: 'var(--accent-cyan)' },
    { label: 'Max Drawdown', value: `${(portfolio.drawdown_pct || 0).toFixed(2)}%`, color: portfolio.drawdown_pct < 10 ? 'var(--accent-green)' : 'var(--accent-red)' },
    { label: 'Balance', value: `$${(portfolio.balance || 0).toLocaleString('en', { maximumFractionDigits: 2 })}`, color: 'var(--text-primary)' },
  ];

  return (
    <div className="card">
      <div className="card-title">Performance</div>
      {items.map(item => (
        <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
          <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{item.label}</span>
          <span style={{ color: item.color, fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 13 }}>{item.value}</span>
        </div>
      ))}
    </div>
  );
}

// ── Footer ───────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer style={{
      borderTop: '1px solid var(--border)',
      padding: '16px 24px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      background: 'var(--bg-glass)',
      backdropFilter: 'blur(20px)',
    }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
        QuantBot Pro — Paper Trading (Demo Mode)
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
        EMA20/200 × 5m Filter × RandomForest ML
      </div>
    </footer>
  );
}
