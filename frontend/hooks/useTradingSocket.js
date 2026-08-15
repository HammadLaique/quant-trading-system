/**
 * Custom React hook for managing the WebSocket connection to the backend.
 * Handles auto-reconnect, message parsing, and state updates.
 */
import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'wss://quant-trading-system-0nf9.onrender.com/ws';
const RECONNECT_DELAY = 3000;

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
  const [ticks, setTicks] = useState({});        // symbol → { price, is_closed }
  const [tradeEvents, setTradeEvents] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        // Send ping every 25s to keep alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 25000);
        ws._pingInterval = pingInterval;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (e) {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        clearInterval(ws._pingInterval);
        // Auto-reconnect
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    }
  }, []);

  // Fetch initial market prices so coins never stay stuck on Loading
  useEffect(() => {
    const fetchInitialPrices = async () => {
      const urls = [
        'https://data-api.binance.vision/api/v3/ticker/price',
        'https://api.binance.com/api/v3/ticker/price',
      ];
      for (const url of urls) {
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
            setTicks(prev => ({ ...tickMap, ...prev }));
            break;
          }
        } catch (e) {
          // try next url
        }
      }
    };
    fetchInitialPrices();
    const interval = setInterval(fetchInitialPrices, 10000); // refresh every 10s as background fallback
    return () => clearInterval(interval);
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
          open_positions: Array.isArray(data.open_positions) ? data.open_positions.length : (data.open_positions ?? prev.open_positions),
          total_trades: data.total_trades ?? prev.total_trades,
          equity_curve: data.equity_curve ?? prev.equity_curve,
          open_positions_list: Array.isArray(data.open_positions) ? data.open_positions : prev.open_positions_list,
          recent_trades: data.recent_trades ?? prev.recent_trades,
          strategy_status: data.strategy_status ?? prev.strategy_status,
        }));
        break;

      case 'tick':
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
