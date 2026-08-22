/**
 * Custom React hook for managing the WebSocket connection to the backend.
 * Uses Binance FUTURES prices (fapi.binance.com) for initial price seed.
 * WebSocket ticks from the backend stream update prices in real-time.
 * REST polling is only done ONCE on mount — WS is the live price source.
 */
import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'wss://quant-trading-system-0nf9.onrender.com/ws';
const RECONNECT_DELAY = 3000;

// Binance Futures price endpoint (no API key needed)
const FUTURES_PRICE_URLS = [
  'https://fapi.binance.com/fapi/v1/ticker/price',
  'https://fapi1.binance.com/fapi/v1/ticker/price',
];

export function useTradingSocket() {
  const [connected, setConnected] = useState(false);
  const [portfolio, setPortfolio] = useState({
    balance: 100000,
    equity: 100000,
    total_pnl: 0,
    total_pnl_pct: 0,
    total_r: 0,
    win_rate: 0,
    profit_factor: 0,
    drawdown_pct: 0,
    open_positions: 0,
    total_trades: 0,
    equity_curve: [],
    open_positions_list: [],
    recent_trades: [],
    strategy_status: [],
  });
  const [ticks, setTicks] = useState({});
  const [tradeEvents, setTradeEvents] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  // Track whether WS ticks have started flowing — avoid overwriting with stale REST data after that
  const wsTicksActive = useRef(false);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        wsTicksActive.current = false;
        // Keepalive ping every 25s
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 25000);
        ws._pingInterval = pingInterval;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // Mark WS ticks as active once we get the first tick
          if (data?.type === 'tick') wsTicksActive.current = true;
          handleMessage(data);
        } catch (e) {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsTicksActive.current = false;
        clearInterval(ws._pingInterval);
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    }
  }, []);

  // Seed initial prices ONCE from Binance FUTURES REST API on mount.
  // After WebSocket ticks start flowing, we NEVER overwrite with REST polling.
  useEffect(() => {
    const seedFuturesPrices = async () => {
      for (const url of FUTURES_PRICE_URLS) {
        try {
          const res = await fetch(url);
          if (res.ok) {
            const data = await res.json();
            const tickMap = {};
            for (const item of data) {
              if (item.symbol?.endsWith('USDT')) {
                tickMap[item.symbol] = { price: parseFloat(item.price), is_closed: false };
              }
            }
            // Only set seed prices if WebSocket hasn't started delivering ticks yet
            setTicks(prev => {
              if (wsTicksActive.current) return prev; // WS is live — don't overwrite
              return { ...tickMap, ...prev };
            });
            break;
          }
        } catch (e) {
          // try next url
        }
      }
    };

    seedFuturesPrices();
    // No polling interval — WebSocket is the real-time source after first load
  }, []);

  const handleMessage = (data) => {
    if (!data?.type) return;

    switch (data.type) {
      case 'portfolio':
      case 'init':
        setPortfolio(prev => ({
          ...prev,
          balance: data.balance ?? prev.balance,
          equity: data.equity ?? prev.equity,
          total_pnl: data.total_pnl ?? prev.total_pnl,
          total_pnl_pct: data.total_pnl_pct ?? prev.total_pnl_pct,
          total_r: data.total_r ?? prev.total_r,
          win_rate: data.win_rate ?? prev.win_rate,
          profit_factor: data.profit_factor ?? prev.profit_factor,
          drawdown_pct: data.drawdown_pct ?? prev.drawdown_pct,
          open_positions: Array.isArray(data.open_positions)
            ? data.open_positions.length
            : (data.open_positions ?? prev.open_positions),
          total_trades: data.total_trades ?? prev.total_trades,
          equity_curve: data.equity_curve ?? prev.equity_curve,
          open_positions_list: Array.isArray(data.open_positions)
            ? data.open_positions
            : prev.open_positions_list,
          recent_trades: data.recent_trades ?? prev.recent_trades,
          strategy_status: data.strategy_status ?? prev.strategy_status,
        }));
        break;

      case 'tick':
        // Real-time price tick from Binance Futures WebSocket — highest priority update
        if (data.symbol) {
          setTicks(prev => ({
            ...prev,
            [data.symbol]: { price: data.price, is_closed: data.is_closed },
          }));
        }
        break;

      case 'trade_event':
        setTradeEvents(prev => [data, ...prev].slice(0, 50));
        break;

      default:
        break;
    }
  };

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected, portfolio, ticks, tradeEvents };
}
