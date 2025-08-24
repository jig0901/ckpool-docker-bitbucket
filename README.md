# 📊 Mining Metrics API & Nginx Proxy

This repository provides a **Dockerized FastAPI service** and **Nginx proxy** for exposing real-time solo mining statistics from [CKPool](https://bitbucket.org/ckolivas/ckpool/src/master/).  
With this setup, you can monitor **hashrates, shares, worker performance, and solo odds** while also pulling **live ComEd electricity prices** to track mining economics.

---

## 🛠️ Enhancements in This Setup

Compared to a vanilla CKPool build, this repo includes **additional enhancements**:

### ✅ Stratifier.c Modifications
- Added **structured metrics emission** (`metrics_emit`) that outputs log lines prefixed with `METRIC …`.  
- Injected into `block_update()` to emit compact **workinfo snapshots** on each new block/update.  
  - Drops heavy fields (`transactiontree`, `transactions`, `merkles`) to keep logs lean.  
  - Adds `txcount` summary.  
  - Logs JSON metrics with pool, timestamp, and type for external parsers.  
- Enables downstream apps (like the FastAPI service) to parse mining stats in near real time without parsing raw stratum chatter.

📌 The modified CKPool source used for this build is maintained in a **Bitbucket fork** here:  
👉 [Modified CKPool with Stratifier Enhancements](https://bitbucket.org/jbelani/ckpool/src/master/)  

This fork is used in the Docker build pipeline for CKPool integration.

### ✅ FastAPI Metrics Service
- `GET /metrics` – Aggregated stats from `ckpool.log`:  
  hashrate windows, per-worker summaries, shares, odds, pool snapshot.
- `GET /comed-prices` – Fetches ComEd 5-min electricity prices (Chicago time).

### ✅ Robust Log Parser
- Multi-line `METRIC {…}` parsing with interleaved line handling.
- Extracts **shares, user summaries, per-worker stats, pool snapshots**.
- Aggregates for `last_10m`, `last_1h`, `best_sdiff_24h`, grouped counts by agent/worker.

### ✅ Solo Odds Calculator
- Computes probability of block discovery using your hashrate vs network difficulty.
- Pulls difficulty from Bitcoin Core RPC (`getdifficulty`) or from logs as fallback.

### ✅ Nginx Reverse Proxy
- TLS + CORS proxy in front of API service.
- Exposes browser-friendly endpoints at `/metrics/` and `/comed-prices/`.

---

## 📦 Features

- Minimal deployment with Docker & Compose
- Reads CKPool logs live (auto-detects newest log on rotation)
- Compatible with Bitcoin Core full node
- Exposes clean JSON API for dashboards & front-ends
- Built-in CORS support via Nginx

---

## 🚀 Getting Started

### 🔨 Build the Docker Image

```bash
docker build -t mining-metrics-api .
```

### ▶️ Run with Docker Compose

```bash
docker-compose up -d
```

This starts:
- **metrics_api** (FastAPI service on port `8000`)  
- **nginx** (reverse proxy on ports `80`/`443`)  

Logs and RPC creds are passed via environment or `config.yaml`.

---

## ⛏️ Configuration

### 🗂️ `config.yaml` (optional)

```yaml
log_path: /ckpool/logs/ckpool.log
btc_address: "bc1q..."
rpc_user: "InventorX"
rpc_password: "********"
rpc_host: "10.0.0.2"
rpc_port: 8332
```

### 🌍 Environment Variables

- `CKPOOL_LOG_FILE` – direct file path (highest priority)  
- `CKPOOL_LOG_DIR` – auto-select newest `ckpool*.log*`  
- `BTC_ADDRESS` – wallet address filter  
- `RPC_USER`, `RPC_PASSWORD`, `RPC_HOST`, `RPC_PORT` – Bitcoin Core RPC access  

---

## ⚙️ Nginx Proxy

- Proxies:
  - `/metrics/` → `http://metrics_api:8000/metrics`
  - `/comed-prices/` → `http://metrics_api:8000/comed-prices`
- Adds CORS headers for browser apps
- Handles HTTPS with your certs (`/etc/nginx/ssl/`)

---

## 🛠️ File Structure

```
.
├── Dockerfile          # API build instructions
├── docker-compose.yml  # Service definitions (API + Nginx)
├── nginx.conf          # Reverse proxy + CORS
├── api.py              # FastAPI app
├── ckpool_parser.py    # Parser for ckpool logs
└── README.md           # This file
```

---

## 📚 Reference

- Original Project: [CKPool by Ckolivas](https://bitbucket.org/ckolivas/ckpool/)  
- Modified Fork: [Jbelani CKPool Bitbucket Fork](https://bitbucket.org/jbelani/ckpool/src/master/)  
- ComEd API: 5-minute real-time pricing feed  
- FastAPI: [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com)

---

## 💬 Credits

- Based on [CKolivas’s CKPool](https://bitbucket.org/ckolivas/ckpool/)  
- Stratifier metrics + API & Dockerization by **[Your Name/GitHub handle]**

---

## 📜 License

MIT (or upstream CKPool license for inherited code)
