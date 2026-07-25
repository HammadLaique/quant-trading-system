# QuantBot Pro - Autonomous Leveraged Crypto Trading System

An enterprise-grade, high-frequency quant trading system that tracks the **top 100 cryptocurrencies** by 24-hour volume on Binance, makes leveraged paper-trading decisions using custom indicators combined with a machine learning classification engine, and serves a premium dark-themed dashboard.

## 🚀 Quick Start (Local Setup)

The entire project is pre-configured to run from **Disk D:** (`D:\quant_trading_system`).

### 1. Pre-Train the Machine Learning Models
Before launching the live trading system, you must train the Random Forest models. This fetches 90 days of 1-minute historical data per coin, calculates features, applies SMOTE class balancing, and saves the trained models.

Double-click or run:
```bash
D:\quant_trading_system\train_all.bat
```
*Note: Already trained coins (like BTC, ETH) will be skipped on subsequent runs. You can stop training at any time with `Ctrl+C`; any partially trained models will be saved.*

### 2. Launch the System (Backend + Frontend)
Once the models are trained, you can start the entire system with one command. This launches the Python FastAPI backend (which connects to the Binance live WebSocket streams) and the Next.js dev server.

Double-click or run:
```bash
D:\quant_trading_system\start_all.bat
```

### 3. Open the Dashboard
* **Dashboard (Next.js Frontend)**: [http://localhost:3000](http://localhost:3000)
* **Backend REST API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Live System Logs**: `D:\quant_trading_system\logs\`

---

## 🛠️ System Architecture

```mermaid
graph TD
    subgraph Live Backend (FastAPI)
        BinanceWS[Binance Live WebSocket] -->|1m Candlestick Stream| Runner[Strategy Runner]
        Runner -->|Candle Buffers| Indicators[Technical Feature Engineering]
        Indicators -->|Feature Vectors| ML[RandomForest ML Gate]
        ML -->|Confidence Score| Strategy[EMA Crossover Logic]
        Strategy -->|Open/Close signals| OM[Order Manager]
        OM -->|Execute Leveraged Trade| Portfolio[In-Memory Paper Account]
    end

    subgraph Live Dashboard (Next.js)
        WSClient[React WebSocket Hook] <-->|Real-Time State Broadcast| API[FastAPI WebServer]
        UI[Premium Dark Theme Layout] -->|Visualizes Data| WSClient
    end
    
    API <-->|State & Stats JSON| OM
```

### Key Modules:
* **`backend/main.py`**: Entry point. Sets up server endpoints, starts background lifespan routing, and reconfigures console encoding to UTF-8 to prevent terminal errors.
* **`backend/strategies/ema_ml_strategy.py`**: Per-coin strategy coordinator. Houses a 1,500 1-minute candle rolling buffer. Evaluates signals on candle closures.
* **`backend/features/engineering.py`**: Calculates EMA20, EMA200, 5-minute EMA200 trend filter, ATR, MACD, slopes, price momentum, volatility, and MACD divergence.
* **`backend/ml/`**: Model trainer and predictor. Runs `RandomForestClassifier` with balanced class weights.
* **`backend/core/order_manager.py`**: Monitors open positions on every price tick. Handles stop-losses, take-profits (1:2 R:R), breakeven trailing, and liquidation checks.
* **`backend/core/portfolio.py`**: Tracks account equity curves, win/loss history, margins, and active open positions.

---

## ⚙️ Configuration & Customization

You can customize risk limits and strategy settings inside the global configuration file:
* **File**: `D:\quant_trading_system\.env`

### Important Settings:
* `INITIAL_BALANCE_USDT`: Starting paper money (Default: `$100,000`)
* `DEFAULT_LEVERAGE`: Leverage multiplier used for execution (Default: `10x`, Max: `50x`)
* `RISK_PER_TRADE_PERCENT`: Risk allocation percentage per trade (Default: `1.0%` of current balance)
* `WIN_PROB_THRESHOLD`: Min probability output from RandomForest to permit a trade (Default: `0.52`)
* `TOP_N_COINS`: Total assets tracked from volume tickers (Default: `100` coins)

---

## 🌐 Production & Vercel Deployment

### 1. Deploy the Frontend on Vercel
1. Upload the `frontend` folder to a GitHub repository.
2. Connect the repository to your Vercel Account.
3. Add the following Environment Variables in the Vercel Dashboard:
   * `NEXT_PUBLIC_API_URL` = `https://your-backend-live-domain.com/api`
   * `NEXT_PUBLIC_WS_URL` = `wss://your-backend-live-domain.com/ws`
4. Click **Deploy**.

### 2. Deploy the Backend
The backend must run on a continuous server (e.g. VPS, EC2, or a dedicated PC) to listen to the Binance WebSocket streams, evaluate strategy conditions, and run model predictions.
1. Run the backend using `python main.py` or compile it into a Docker container.
2. Use a reverse proxy like Nginx with Let's Encrypt SSL configuration to expose the API safely over `https://` / `wss://`.
