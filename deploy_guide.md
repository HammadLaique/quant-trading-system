# ☁️ QuantBot Pro - Cloud Deployment Guide

This guide explains how to deploy the entire Quant Trading System to the cloud for **100% FREE, 24/7 operation**. Once deployed, you can access the dashboard and monitor your trades from any device (phone, laptop, tablet) without leaving your PC turned on.

---

## 🛠️ Step 1: Upload Your Code to GitHub (Do This Once)

To deploy online, your code must be in a GitHub repository.

1. Go to [github.com](https://github.com) and log into your account (create a free account if you don't have one).
2. Create a new **Private** repository named `quant-trading-system`.
3. Open a terminal (PowerShell) on your PC and run these commands to push your project to GitHub:
   ```powershell
   cd D:\quant_trading_system
   git init
   git add .
   git commit -m "Initial commit for cloud deployment"
   git branch -M main
   git remote add origin https://github.com/YOUR_GITHUB_USERNAME/quant-trading-system.git
   git push -u origin main
   ```
   *(Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username).*

---

## 🖥️ Step 2: Deploy the Backend (FastAPI Server)

The backend must run 24/7 to connect to Binance live price streams. We recommend **Render** or **Hugging Face Spaces** (both are free).

### Option A: Render (Easiest - Free)
1. Go to [render.com](https://render.com) and sign up using your GitHub account.
2. Click **New +** and select **Web Service**.
3. Connect your `quant-trading-system` repository.
4. Configure the service:
   * **Name**: `quant-trading-backend`
   * **Language**: `Docker`
   * **Branch**: `main`
   * **Root Directory**: `backend` (This is very important!)
   * **Instance Type**: `Free`
5. Click **Deploy Web Service**.
6. Once deployed, Render will give you a public URL like:
   `https://quant-trading-backend.onrender.com`

---

## 🎨 Step 3: Deploy the Frontend (Next.js Dashboard)

The frontend is deployed to **Vercel** (the creators of Next.js, completely free).

1. Go to [vercel.com](https://vercel.com) and sign up/login with your GitHub account.
2. Click **Add New** -> **Project**.
3. Import your `quant-trading-system` repository.
4. Configure the project:
   * **Framework Preset**: `Next.js`
   * **Root Directory**: `frontend` (Click edit and select the frontend folder!)
5. Expand the **Environment Variables** section and add:
   * `NEXT_PUBLIC_API_URL` = `https://quant-trading-backend.onrender.com/api`
   * `NEXT_PUBLIC_WS_URL` = `wss://quant-trading-backend.onrender.com/ws`
   *(Replace the Render URL with your actual backend URL from Step 2. Note: use `wss://` instead of `https://` for the WS URL).*
6. Click **Deploy**.
7. Vercel will give you a live URL like:
   `https://quant-trading-dashboard.vercel.app`

---

## 💡 Troubleshooting & Cloud Limits

* **Free Tier Sleep**: Render's free tier spins down (goes to sleep) after 15 minutes of no dashboard visits. However, the connection is kept alive when the frontend dashboard is open. If you want it to run 24/7 without sleeping, you can use a free monitoring service like [UptimeRobot](https://uptimerobot.com) to ping your backend URL `https://your-backend.onrender.com/api/health` every 5 minutes.
* **CORS Settings**: The backend is configured to accept connections from any Vercel domain, so your frontend will connect securely.
