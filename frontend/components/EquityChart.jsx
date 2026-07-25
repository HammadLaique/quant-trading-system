/**
 * EquityChart — Renders the portfolio equity curve using Recharts.
 * Shows real-time equity growth over time.
 */
import { useMemo } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';

const INITIAL_BALANCE = 100000;

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const pnl = d.equity - INITIAL_BALANCE;
  return (
    <div style={{
      background: 'var(--bg-elevated)',
      border: '1px solid var(--border-bright)',
      borderRadius: 8,
      padding: '10px 14px',
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
    }}>
      <div style={{ color: 'var(--text-secondary)', marginBottom: 4 }}>{d.time}</div>
      <div style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>
        ${d.equity?.toLocaleString('en', { minimumFractionDigits: 2 })}
      </div>
      <div style={{ color: pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)', marginTop: 2 }}>
        {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} ({((pnl / INITIAL_BALANCE) * 100).toFixed(2)}%)
      </div>
    </div>
  );
};

export default function EquityChart({ equityCurve = [] }) {
  const data = useMemo(() => {
    if (!equityCurve.length) {
      // Placeholder flat line
      return [{ time: 'Start', equity: INITIAL_BALANCE }];
    }
    return equityCurve.slice(-200).map((point, i) => ({
      time: new Date(point.timestamp * 1000).toLocaleTimeString(),
      equity: point.equity,
      index: i,
    }));
  }, [equityCurve]);

  const minEquity = Math.min(...data.map(d => d.equity)) * 0.999;
  const maxEquity = Math.max(...data.map(d => d.equity)) * 1.001;
  const isProfit = data[data.length - 1]?.equity >= INITIAL_BALANCE;

  const gradientColor = isProfit ? '#00ff88' : '#ff3366';

  return (
    <div className="card" style={{ padding: '16px 16px 8px' }}>
      <div className="flex-between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ marginBottom: 0 }}>Equity Curve</div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>
          {equityCurve.length} points
        </div>
      </div>

      <div className="equity-chart">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={gradientColor} stopOpacity={0.25} />
                <stop offset="95%" stopColor={gradientColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="time" hide />
            <YAxis
              domain={[minEquity, maxEquity]}
              hide
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={INITIAL_BALANCE}
              stroke="rgba(255,255,255,0.1)"
              strokeDasharray="4 4"
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke={gradientColor}
              strokeWidth={2}
              fill="url(#equityGradient)"
              dot={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
