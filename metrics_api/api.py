import os
import math
import glob
import yaml
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import httpx
import time
import pytz

from fastapi import FastAPI
from bitcoinrpc.authproxy import AuthServiceProxy

from ckpool_parser import get_user_stats

central = pytz.timezone("America/Chicago")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
app = FastAPI()

# ---------- config & env overrides ----------
cfg_path = Path(__file__).parent / "config.yaml"
cfg = {}
if cfg_path.exists():
    try:
        cfg = yaml.safe_load(cfg_path.read_text()) or {}
    except Exception as e:
        logging.warning(f"Config load failed: {e}")

ENV_LOG_FILE = os.getenv("CKPOOL_LOG_FILE", "").strip()
ENV_LOG_DIR  = os.getenv("CKPOOL_LOG_DIR", "").strip()
ENV_ADDR     = os.getenv("BTC_ADDRESS", "").strip()

def resolve_log_path() -> str:
    # 1) explicit file wins
    if ENV_LOG_FILE and Path(ENV_LOG_FILE).is_file():
        return ENV_LOG_FILE
    # 2) directory -> pick newest ckpool*.log
    if ENV_LOG_DIR and Path(ENV_LOG_DIR).exists():
        candidates = sorted(
            glob.glob(str(Path(ENV_LOG_DIR) / "ckpool*.log*")),
            key=lambda p: Path(p).stat().st_mtime,
            reverse=True
        )
        if candidates:
            return candidates[0]
        # common default
        default = str(Path(ENV_LOG_DIR) / "ckpool.log")
        return default
    # 3) fall back to config.yaml
    return cfg.get("log_path", "/ckpool/logs/ckpool.log")

def resolve_btc_address() -> str:
    if ENV_ADDR:
        return ENV_ADDR
    return (cfg.get("btc_address") or "").strip()

LOG_PATH    = resolve_log_path()
BTC_ADDRESS = resolve_btc_address()

RPC_USER = os.getenv("RPC_USER", cfg.get("rpc_user", ""))
RPC_PASS = os.getenv("RPC_PASSWORD", cfg.get("rpc_password", ""))
RPC_HOST = os.getenv("RPC_HOST", cfg.get("rpc_host", "127.0.0.1"))
RPC_PORT = int(os.getenv("RPC_PORT", cfg.get("rpc_port", 8332)))

rpc_url = f"http://{RPC_USER}:{RPC_PASS}@{RPC_HOST}:{RPC_PORT}"
rpc = AuthServiceProxy(rpc_url) if RPC_USER and RPC_PASS else None

def parse_hashrate_to_hs(val: str) -> float:
    try:
        s = str(val).replace(',', '').strip().upper()
        import re
        m = re.match(r"([0-9.]+)\s*([KMGTP]?)(?:H/S)?", s)
        if not m:
            return 0.0
        num = float(m.group(1))
        unit = m.group(2) or ""
        mul = {"":1, "K":1e3, "M":1e6, "G":1e9, "T":1e12, "P":1e15}[unit]
        return num * mul
    except Exception:
        return 0.0

async def fetch_comed_prices():
    try:
        url = "https://hourlypricing.comed.com/api?type=5minutefeed"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
        now_ms = int(time.time()*1000)
        # keep last 10 minutes
        recent = [d for d in data if int(d.get("millisUTC", 0)) >= (now_ms - 10*60*1000)]
        out = []
        for d in recent:
            ts = int(d["millisUTC"])/1000.0
            dt = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.utc).astimezone(central)
            out.append({"time": dt.strftime("%H:%M"), "price": d["price"]})
        return out
    except Exception as e:
        logging.error(f"fetch_comed_prices error: {e}")
        return []

@app.get("/metrics")
async def metrics():
    # (re)resolve on every hit so you can swap volumes without reboot
    log_path = resolve_log_path()
    address  = resolve_btc_address()

    st = get_user_stats(log_path, address) or {}

    # hashrates to TH/s
    hr1m = parse_hashrate_to_hs(st.get("hashrate1m", "0")) / 1e12
    hr5m = parse_hashrate_to_hs(st.get("hashrate5m", "0")) / 1e12
    hr1h = parse_hashrate_to_hs(st.get("hashrate1hr","0")) / 1e12
    hr1d = parse_hashrate_to_hs(st.get("hashrate1d", "0")) / 1e12
    hr7d = parse_hashrate_to_hs(st.get("hashrate7d", "0")) / 1e12

    # difficulty
    difficulty = 0.0
    try:
        if rpc:
            difficulty = float(rpc.getdifficulty())
    except Exception as e:
        logging.error(f"RPC getdifficulty failed: {e}")
    if not difficulty:
        difficulty = float(st.get("difficulty", 0) or 0)

    import math
    def odds(H_hs: float, T_sec: float, D: float) -> float:
        if H_hs <= 0 or D <= 0:
            return 0.0
        lam = H_hs * T_sec / (D * 2**32)
        return (1.0 - math.exp(-lam)) * 100.0

    H_hs_1m = parse_hashrate_to_hs(st.get("hashrate1m","0"))

    seconds = {"1yr":365*24*3600, "24hr":24*3600, "7d":7*24*3600, "30d":30*24*3600}

    return {
        "config": {"log_path": log_path, "btc_address": address},
        "comed_future_prices": await fetch_comed_prices(),

        "worker_count":    st.get("workers", 0),
        "best_shares":     st.get("bestshare", 0),
        "last_share_time": st.get("last_share_time", "N/A"),
        "accepted_shares": st.get("accepted_shares", 0),

        "hashrate_1min_ths": round(hr1m, 3),
        "hashrate_5min_ths": round(hr5m, 3),
        "hashrate_1hr_ths":  round(hr1h, 3),
        "hashrate_1d_ths":   round(hr1d, 3),
        "hashrate_7d_ths":   round(hr7d, 3),

        "odds_1yr_percent":  round(odds(parse_hashrate_to_hs(st.get("hashrate1m","0")), seconds["1yr"], difficulty), 6),
        "odds_24hr_percent": round(odds(parse_hashrate_to_hs(st.get("hashrate1d","0")), seconds["24hr"], difficulty), 6),
        "odds_7d_percent":   round(odds(parse_hashrate_to_hs(st.get("hashrate7d","0")), seconds["7d"], difficulty), 6),
        "odds_30d_percent":  round(odds(parse_hashrate_to_hs(st.get("hashrate7d","0")), seconds["30d"], difficulty), 6),

        "workers":       st.get("worker_stats", []),
        "pool":          st.get("pool", {}),
        "last_workinfo": st.get("last_workinfo", {}),
        "recent_shares": st.get("recent_shares", []),
        "share_agg":     st.get("share_agg", {}),
    }
