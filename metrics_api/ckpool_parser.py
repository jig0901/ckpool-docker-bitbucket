import re
import json
import time
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List, Tuple

def _strip_ts_prefix(line: str) -> str:
    """Strip leading `[YYYY-mm-dd HH:MM:SS.mmm] ` if present."""
    try:
        rb = line.index('] ')
        return line[rb + 2:]
    except ValueError:
        return line

def _brace_delta(s: str) -> int:
    return s.count('{') - s.count('}')

def _iter_metric_events(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Parse `METRIC {...}` entries even when JSON spans multiple lines and
    when a new METRIC appears before the prior JSON closes.
    Strategy:
      - Start collecting at 'METRIC ' + first '{'
      - Track brace balance
      - If another 'METRIC ' appears before balance is zero, discard the
        incomplete pending object (it was likely superseded) and start fresh.
    """
    events: List[Dict[str, Any]] = []
    pending = None
    need = 0

    for raw in lines:
        content = _strip_ts_prefix(raw).strip()

        # New METRIC while pending -> abandon the incomplete one (stratifier emitted a new record)
        if pending is not None and content.startswith('METRIC '):
            pending = None
            need = 0  # reset and treat this as a fresh METRIC line

        if pending is not None:
            frag = content
            pending += frag
            need += _brace_delta(frag)
            if need <= 0:
                try:
                    events.append(json.loads(pending))
                except json.JSONDecodeError:
                    # Best-effort sanitize
                    try:
                        sanitized = pending.replace('}"{', '},"{').replace('}\n{', '},{')
                        events.append(json.loads(sanitized))
                    except Exception:
                        pass
                pending, need = None, 0
            continue

        if 'METRIC ' in content:
            frag = content.split('METRIC ', 1)[1].lstrip()
            if not frag.startswith('{'):
                i = frag.find('{')
                if i >= 0:
                    frag = frag[i:]
                else:
                    continue
            pending = frag
            need = _brace_delta(frag)
            if need <= 0:
                try:
                    events.append(json.loads(pending))
                except json.JSONDecodeError:
                    pass
                pending, need = None, 0

    return events

def _parse_pool_line(json_text: str) -> Dict[str, Any]:
    try:
        return json.loads(json_text)
    except Exception:
        return {}

def get_user_stats(log_path: str, btc_address: str, share_limit: int = 100) -> Dict[str, Any]:
    stats = {
        "last_share_time": "N/A",
        "accepted_shares": 0,
        "hashrate1m": "0",
        "hashrate5m": "0",
        "hashrate1hr": "0",
        "hashrate1d": "0",
        "hashrate7d": "0",
        "workers": 0,
        "bestshare": 0,
        "difficulty": 0,
        "worker_stats": [],
        "pool": {},
        "last_workinfo": {},
        "recent_shares": [],
        "share_agg": {},
    }

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return stats

    # 1) METRIC events
    metric_events = _iter_metric_events(lines)

    shares: List[Dict[str, Any]] = []
    last_ts_seen = 0
    addr = (btc_address or "").strip()

    for ev in metric_events:
        t = ev.get("type")
        if t == "share":
            # accept if username matches OR workername startswith "<addr>."
            uname = (ev.get("username") or "").strip()
            wname = (ev.get("workername") or "").strip()
            take = False
            if addr:
                take = (uname == addr) or (wname.startswith(addr + "."))
            else:
                take = True  # no filter if no address provided

            if take:
                s = {
                    "ts":        int(ev.get("ts", 0) or 0),
                    "workinfoid": ev.get("workinfoid"),
                    "clientid":  ev.get("clientid"),
                    "enonce1":   ev.get("enonce1"),
                    "nonce2":    ev.get("nonce2"),
                    "nonce":     ev.get("nonce"),
                    "ntime":     ev.get("ntime"),
                    "diff":      ev.get("diff"),
                    "sdiff":     float(ev.get("sdiff", 0) or 0),
                    "hash":      ev.get("hash"),
                    "result":    bool(ev.get("result", False)),
                    "errn":      ev.get("errn"),
                    "workername": wname,
                    "agent":     ev.get("agent"),
                    "address":   ev.get("address"),
                }
                shares.append(s)
                last_ts_seen = max(last_ts_seen, s["ts"])

        elif t == "workinfo":
            wi = {
                "ts":         int(ev.get("ts", 0) or 0),
                "workinfoid": ev.get("workinfoid"),
                "pool":       ev.get("pool"),
                "poolinstance": ev.get("poolinstance"),
                "prevhash":   ev.get("prevhash"),
                "version":    ev.get("version"),
                "ntime":      ev.get("ntime"),
                "bits":       ev.get("bits"),
                "reward":     ev.get("reward"),
            }
            # keep the most recent snapshot
            if wi["ts"] >= stats["last_workinfo"].get("ts", 0) if stats["last_workinfo"] else True:
                stats["last_workinfo"] = wi
                last_ts_seen = max(last_ts_seen, wi["ts"])

    shares.sort(key=lambda s: s["ts"], reverse=True)
    if share_limit:
        shares = shares[:share_limit]
    stats["recent_shares"] = shares

    # 2) Latest User/Worker summaries
    worker_records: List[Dict[str, Any]] = []
    user_data = None

    for line in reversed(lines):
        content = _strip_ts_prefix(line)
        if content.startswith("Worker "):
            m = re.search(r'Worker\s+[^:]+:(\{.*\})\s*$', content)
            if m:
                try:
                    worker_records.append(json.loads(m.group(1)))
                except Exception:
                    pass
            continue

        if addr and content.startswith("User ") and (addr in content):
            m = re.search(rf'User\s+{re.escape(addr)}:(\{{.*\}})\s*$', content)
            if m:
                try:
                    user_data = json.loads(m.group(1))
                    break
                except Exception:
                    pass

    if user_data:
        lastshare_ts = int(user_data.get("lastshare", 0) or 0)
        stats["last_share_time"] = datetime.fromtimestamp(lastshare_ts).strftime("%Y-%m-%d %H:%M:%S")
        stats["accepted_shares"] = user_data.get("shares", 0)
        stats["hashrate1m"] = user_data.get("hashrate1m", "0")
        stats["hashrate5m"] = user_data.get("hashrate5m", "0")
        stats["hashrate1hr"] = user_data.get("hashrate1hr", "0")
        stats["hashrate1d"] = user_data.get("hashrate1d", "0")
        stats["hashrate7d"] = user_data.get("hashrate7d", "0")
        stats["workers"] = user_data.get("workers", 0)
        stats["bestshare"] = user_data.get("bestshare", 0)
        stats["difficulty"] = user_data.get("difficulty", 0)

    stats["worker_stats"] = worker_records

    # 3) Pool: {...} summaries (merge the most recent values)
    pool_accum: Dict[str, Any] = {}
    for line in reversed(lines):
        content = _strip_ts_prefix(line).strip()
        if not content.startswith("Pool:"):
            continue
        j = content.split("Pool:", 1)[1].strip()
        pobj = _parse_pool_line(j)
        if pobj:
            pool_accum.update(pobj)

            if {"runtime", "lastupdate", "Users", "Workers"}.issubset(pool_accum.keys()) \
               and {"hashrate1m", "hashrate5m", "hashrate15m", "hashrate1hr",
                    "hashrate6hr", "hashrate1d", "hashrate7d"}.issubset(pool_accum.keys()) \
               and {"accepted", "rejected", "bestshare"}.issubset(pool_accum.keys()):
                break

    if pool_accum:
        pool_out = {}
        for k_src, k_dst in [
            ("runtime", "runtime"), ("lastupdate", "lastupdate"),
            ("Users", "users"), ("Workers", "workers"),
            ("Idle", "idle"), ("Disconnected", "disconnected")
        ]:
            if k_src in pool_accum: pool_out[k_dst] = pool_accum[k_src]

        for k in ["hashrate1m","hashrate5m","hashrate15m","hashrate1hr","hashrate6hr","hashrate1d","hashrate7d"]:
            if k in pool_accum: pool_out[k] = pool_accum[k]

        for k in ["diff","accepted","rejected","bestshare","SPS1m","SPS5m","SPS15m","SPS1h"]:
            if k in pool_accum: pool_out[k] = pool_accum[k]

        stats["pool"] = pool_out

    # 4) Aggregates
    by_agent = defaultdict(int)
    by_worker = defaultdict(int)
    for s in shares:
        if s.get("agent"): by_agent[s["agent"]] += 1
        if s.get("workername"): by_worker[s["workername"]] += 1

    ref = last_ts_seen or int(time.time())
    def _agg(window_sec: int) -> Tuple[int, float]:
        lo = ref - window_sec
        vals = [s["sdiff"] for s in shares if s["ts"] >= lo]
        return len(vals), (sum(vals)/len(vals) if vals else 0.0)

    c10, a10 = _agg(10*60)
    c1h, a1h = _agg(60*60)
    last24 = [s["sdiff"] for s in shares if s["ts"] >= ref - 24*3600]
    best24 = max(last24) if last24 else 0.0

    stats["share_agg"] = {
        "last_10m": {"count": c10, "avg_sdiff": round(a10, 3)},
        "last_1h":  {"count": c1h, "avg_sdiff": round(a1h, 3)},
        "best_sdiff_24h": round(best24, 3),
        "by_agent": dict(sorted(by_agent.items(), key=lambda kv: kv[1], reverse=True)),
        "by_worker": dict(sorted(by_worker.items(), key=lambda kv: kv[1], reverse=True)),
    }

    return stats
