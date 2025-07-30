# 🧱 CKPool Solo Mining – Dockerized

This repository provides a fully Dockerized setup of [CKPool](https://bitbucket.org/ckolivas/ckpool/src/master/), a lightweight solo mining stratum server for Bitcoin. With this setup, you can deploy your own solo mining pool instance easily and mine directly to your Bitcoin node.

---

## 🛠️ Enhancements in This Fork

This repository is a fork of the original [CKPool repo](https://bitbucket.org/ckolivas/ckpool/) with **additional enhancements**:

### ✅ Added Worker Detail Logging

In `stratifier.c`, the following block was introduced to emit **per-worker stats to the console/logs**:

```c
/* — emit per‑worker stats to console — */
{
    char *ws, *wsp;

    ws = json_dumps(wval,
                    JSON_NO_UTF8
                  | JSON_PRESERVE_ORDER
                  | JSON_COMPACT);

    ASPRINTF(&wsp, "Worker %s:%s",
             worker->workername, ws);

    dealloc(ws);

    add_msg_entry(&char_list, &wsp);
}
```

This allows the log to output the detailed hashrate, shares, and identity of each connected worker—perfect for solo miners tracking performance.

---

## 📦 Features

- Minimal, fast deployment using Docker
- Runs original CKPool from Ckolivas Bitbucket repo
- Easily configurable via `ckpool.conf`
- Automatically launches CKPool on container startup
- Exposes stratum port `3333` for miner connection

---

## 🚀 Getting Started

### 🔨 Build the Docker Image

```bash
docker build -t ckpool-solo .
```

### ▶️ Run the Container

```bash
docker run -d --name ckpool -p 3333:3333 ckpool-solo
```

---

## ⛏️ Miner Configuration

Configure your ASIC or mining software with the following:

```
URL:      stratum+tcp://<host-ip>:3333
Username: <your-BTC-wallet-address>
Password: x
```

✅ Make sure your miner's IP is allowed to connect to the host running this container.

---

## 🔗 Bitcoin Node Requirements

Your Bitcoin Core node **must be running in full mode** and be:

- **Fully synced**
- **RPC accessible** at `10.229.65.150` or your configured IP
- Proper `bitcoin.conf` setup with:
  ```ini
  server=1
  rpcuser=InventorX
  rpcpassword=<your-password>
  rpcallowip=172.17.0.0/16
  ```
- Port `8332` (RPC) must be reachable from this container

---

## ⚙️ Configuration Files

- `ckpool.conf.example`: Example pool config
- `start.sh`: Alternate manual start script
- `entrypoint.sh`: Auto-start script used by Docker

---

## 🛠️ File Structure

```
.
├── Dockerfile          # Build instructions
├── entrypoint.sh       # Runs ckpool on container start
├── start.sh            # Optional manual run script
├── ckpool.conf.example # Sample config
└── README.md           # This file
```

---

## 📚 Reference

- Original Project: [CKPool by Ckolivas](https://bitbucket.org/ckolivas/ckpool/)
- GBT Source Required: Full Bitcoin Core node with `-rpc` enabled

---

## 💬 Credits

- Based on [CKolivas's CKPool](https://bitbucket.org/ckolivas/ckpool/)
- Dockerization and enhancements by [Your Name or GitHub handle]

---

## 📜 License

This project follows the license of the upstream CKPool repo. Please review the Bitbucket source for applicable terms.




