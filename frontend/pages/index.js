/**
 * Main Dashboard Page
 * Real-time autonomous trading bot dashboard — QuantBot Pro
 */
import Head from 'next/head';
import { useEffect, useState, useCallback } from 'react';
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
  const [closeToast, setCloseToast] = useState(null); // { msg, ok }

  // Fetch coin universe once on mount
  useEffect(() => {
    fetch(`${API_URL}/coins`)
      .then(r => r.json())
      .then(d => { if (d.coins?.length) setCoins(d.coins); })
      .catch(() => {});
  }, []);

  // Fallback coin list
  const DEFAULT_COINS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "SHIBUSDT", "DOTUSDT",
    "LINKUSDT", "NEARUSDT", "SUIUSDT", "PEPEUSDT", "LTCUSDT",
    "UNIUSDT", "APTUSDT", "FETUSDT", "TAOUSDT", "TRXUSDT",
  ];
  const wsCoins = (portfolio.strategy_status || []).map(s => s.symbol);
  const displayCoins = coins.length > 0 ? coins : (wsCoins.length > 0 ? wsCoins : DEFAULT_COINS);

  const openPositions = portfolio.open_positions_list || [];
  const posCount = openPositions.length;

  // ── Force-close handler ────────────────────────────────────────────────────
  const handleForceClose = useCallback(async (pos) => {
    try {
      const res = await fetch(`${API_URL}/positions/${pos.id}/close`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setCloseToast({ msg: `✓ ${pos.symbol?.replace('USDT', '')} closed at $${data.exit_price?.toFixed ? data.exit_price.toFixed(4) : data.exit_price} | P&L: ${data.pnl_usdt >= 0 ? '+' : ''}$${data.pnl_usdt?.toFixed(2)}`, ok: true });
      } else {
        setCloseToast({ msg: `✕ Failed to close ${pos.symbol?.replace('USDT', '')}: ${data.detail || 'Unknown error'}`, ok: false });
      }
    } catch (e) {
      setCloseToast({ msg: `✕ Network error closing position`, ok: false });
    }
    setTimeout(() => setCloseToast(null), 4000);
  }, []);

  // ── Tab config ─────────────────────────────────────────────────────────────
  const TABS = [
    { id: 'overview',   label: 'Overview',   icon: '⬡' },
    { id: 'positions',  label: 'Positions',  icon: '◈', badge: posCount },
    { id: 'coins',      label: 'Coins',      icon: '◎', badge: displayCoins.length },
    { id: 'trades',     label: 'History',    icon: '◷' },
  ];

  return (
    <>
      <Head>
        <title>QuantBot Pro — Autonomous Crypto Trading</title>
        <meta name="description" content="Real-time autonomous cryptocurrency trading bot dashboard with ML-powered signals across top trending coins." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="layout">
        <Navbar portfolio={portfolio} connected={connected} />

        <main className="main-content">
          {/* KPI Stats Row */}
          <StatsRow portfolio={portfolio} />

          {/* Tab Navigation */}
          <nav className="tab-nav" role="tablist">
            {TABS.map(tab => (
              <button
                key={tab.id}
                id={`tab-${tab.id}`}
                role="tab"
                aria-selected={activeTab === tab.id}
                className={`tab-btn${activeTab === tab.id ? ' active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <span>{tab.icon}</span>
                {tab.label}
                {tab.badge !== undefined && (
                  <span className={`tab-badge${!tab.badge ? ' zero' : ''}`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            ))}
          </nav>

          {/* ── Overview Tab ─────────────────────────────────────────────── */}
          {activeTab === 'overview' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16, marginTop: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <EquityChart equityCurve={portfolio.equity_curve} />
                <OpenPositions
                  positions={openPositions}
                  ticks={ticks}
                  onForceClose={handleForceClose}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <TradeFeed trades={portfolio.recent_trades || []} />
                <StrategyStatus strategies={portfolio.strategy_status || []} />
              </div>
            </div>
          )}

          {/* ── Positions Tab ─────────────────────────────────────────────── */}
          {activeTab === 'positions' && (
            <div style={{ marginTop: 16 }}>
              <OpenPositions
                positions={openPositions}
                ticks={ticks}
                onForceClose={handleForceClose}
              />
            </div>
          )}

          {/* ── Coins Tab ─────────────────────────────────────────────────── */}
          {activeTab === 'coins' && (
            <div style={{ marginTop: 16 }}>
              <CoinGrid
                coins={displayCoins}
                ticks={ticks}
                positions={openPositions}
                strategies={portfolio.strategy_status || []}
              />
            </div>
          )}

          {/* ── History Tab ───────────────────────────────────────────────── */}
          {activeTab === 'trades' && (
            <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16 }}>
              <AllTradesTable trades={portfolio.recent_trades || []} />
              <TradeStatsPanel portfolio={portfolio} />
            </div>
          )}
        </main>

        <Footer />
      </div>

      {/* Force-close toast notification */}
      {closeToast && (
        <div style={{
          position: 'fixed', bottom: 28, right: 28, zIndex: 999,
          background: closeToast.ok ? 'rgba(0,255,136,0.12)' : 'rgba(255,51,102,0.12)',
          border: `1px solid ${closeToast.ok ? 'rgba(0,255,136,0.4)' : 'rgba(255,51,102,0.4)'}`,
          color: closeToast.ok ? 'var(--accent-green)' : 'var(--accent-red)',
          padding: '12px 20px',
          borderRadius: 10,
          fontSize: 13,
          fontWeight: 600,
          maxWidth: 380,
          backdropFilter: 'blur(12px)',
          animation: 'slide-in 0.3s ease',
          boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
        }}>
          {closeToast.msg}
        </div>
      )}
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
      <div style={{ display: 'flex', gap: 20, marginBottom: 14 }}>
        {[
          { label: 'Initialized', val: initialized, color: 'var(--accent-cyan)' },
          { label: 'ML Ready',    val: modelReady,  color: 'var(--accent-green)' },
          { label: 'Total Coins', val: strategies.length, color: 'var(--text-primary)' },
        ].map(({ label, val, color }) => (
          <div key={label}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.07em' }}>{label}</div>
            <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>{val}</div>
          </div>
        ))}
      </div>
      <div style={{ height: 5, background: 'var(--bg-elevated)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${strategies.length ? (initialized / strategies.length) * 100 : 0}%`,
          background: 'linear-gradient(90deg, var(--accent-cyan), var(--accent-green))',
          borderRadius: 3,
          transition: 'width 1s ease',
        }} />
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6 }}>Initialization progress</div>
    </div>
  );
}

// ── All Trades Table ─────────────────────────────────────────────────────────
function AllTradesTable({ trades }) {
  return (
    <div className="card">
      <div className="card-title">Trade History</div>
      <div style={{ overflowX: 'auto', maxHeight: 600, overflowY: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Dir</th>
              <th>Lev</th>
              <th>Entry</th>
              <th>Exit</th>
              <th>P&L</th>
              <th>R</th>
              <th>Result</th>
              <th>ML%</th>
            </tr>
          </thead>
          <tbody>
            {[...trades].reverse().map((t, i) => (
              <tr key={`${t.id}-${i}`}>
                <td style={{ fontWeight: 700 }}>{t.symbol?.replace('USDT', '')}</td>
                <td>
                  <span className={`badge badge-${t.direction === 1 ? 'long' : 'short'}`}>
                    {t.direction === 1 ? '▲' : '▼'}
                  </span>
                </td>
                <td style={{ color: 'var(--accent-yellow)', fontFamily: 'var(--font-mono)' }}>{t.leverage}×</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{t.entry_price?.toFixed(4)}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{t.exit_price?.toFixed(4)}</td>
                <td className={t.pnl_usdt >= 0 ? 'positive' : 'negative'} style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                  {t.pnl_usdt >= 0 ? '+' : ''}${t.pnl_usdt?.toFixed(2)}
                </td>
                <td className={t.pnl_r >= 0 ? 'positive' : 'negative'} style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                  {t.pnl_r >= 0 ? '+' : ''}{t.pnl_r?.toFixed(2)}R
                </td>
                <td>
                  <span className={`badge badge-${t.pnl_usdt >= 0 ? 'win' : 'loss'}`}>
                    {t.outcome?.includes('FORCE') ? 'CLOSED' : t.pnl_usdt >= 0 ? 'WIN' : 'LOSS'}
                  </span>
                </td>
                <td style={{ color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)', fontSize: 12 }}>
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
    { label: 'Total Trades',   value: portfolio.total_trades || 0,                                    color: 'var(--text-primary)' },
    { label: 'Win Rate',       value: `${(portfolio.win_rate || 0).toFixed(1)}%`,                     color: (portfolio.win_rate || 0) >= 50 ? 'var(--accent-green)' : 'var(--accent-red)' },
    { label: 'Total R',        value: `${(portfolio.total_r || 0) >= 0 ? '+' : ''}${(portfolio.total_r || 0).toFixed(2)}R`, color: (portfolio.total_r || 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' },
    { label: 'Profit Factor',  value: portfolio.profit_factor === Infinity ? '∞' : (portfolio.profit_factor || 0).toFixed(2), color: 'var(--accent-cyan)' },
    { label: 'Max Drawdown',   value: `${(portfolio.drawdown_pct || 0).toFixed(2)}%`,                 color: (portfolio.drawdown_pct || 0) < 10 ? 'var(--accent-green)' : 'var(--accent-red)' },
    { label: 'Balance',        value: `$${(portfolio.balance || 0).toLocaleString('en', { maximumFractionDigits: 2 })}`, color: 'var(--text-primary)' },
  ];

  return (
    <div className="card">
      <div className="card-title">Performance Summary</div>
      {items.map(item => (
        <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '9px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
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
      padding: '14px 24px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      background: 'var(--bg-glass)',
      backdropFilter: 'blur(20px)',
    }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
        QuantBot Pro — Paper Trading (Demo Mode) · Up to 300 trending coins · Max 20 simultaneous trades
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
        EMA20/200 · 5m Filter · RandomForest ML · 100× Leverage
      </div>
    </footer>
  );
}
