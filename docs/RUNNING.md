# SecureDerm AI — Running the System

## Prerequisites

- Python 3.10+ installed
- Virtual environment activated: `.\venv\Scripts\Activate.ps1`
- Dependencies installed: `pip install -r requirements.txt`

---

## Step 1 — Generate Mock Data

Before running the federated system, create test datasets:

```powershell
cd D:\securederm-ai
python -m scripts.generate_mock_data --hospitals 2 --images-per-class 25
```

This creates:
```
datasets/
  hospital_A/
    normal_healing/      (25 images)
    mild_infection/      (25 images)
    moderate_infection/  (25 images)
    severe_infection/    (25 images)
  hospital_B/
    (same structure)
```

---

## Step 2 — Start the Aggregation Server

Open **Terminal 1**:

```powershell
cd D:\securederm-ai
.\venv\Scripts\Activate.ps1
python -m aggregator.server
```

Expected output:
```
2026-03-07 10:00:00 [INFO] Global model initialized (version 1)
2026-03-07 10:00:00 [INFO] Aggregation server ready on port 8000
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Started server process
```

Verify it's running: open http://127.0.0.1:8000/status in a browser.

---

## Step 3 — Run Hospital Node A

Open **Terminal 2**:

```powershell
cd D:\securederm-ai
.\venv\Scripts\Activate.ps1
python -m hospital_node.client --node hospital_A --rounds 3
```

Expected output:
```
2026-03-07 10:01:00 [hospital_node] Registering node 'hospital_A' ...
2026-03-07 10:01:00 [hospital_node] Registered as hospital_A (model v1)
2026-03-07 10:01:00 [hospital_node] === Round 1/3 ===
2026-03-07 10:01:01 [hospital_node] Downloaded global model v1
2026-03-07 10:01:01 [hospital_node] Starting local training on datasets\hospital_A ...
  Epoch 1/2 — loss: 1.3856
  Epoch 2/2 — loss: 1.2431
2026-03-07 10:01:15 [hospital_node] Update accepted (aggregated=False, model v1)
```

---

## Step 4 — Run Hospital Node B

Open **Terminal 3**:

```powershell
cd D:\securederm-ai
.\venv\Scripts\Activate.ps1
python -m hospital_node.client --node hospital_B --rounds 3
```

Expected output:
```
2026-03-07 10:01:30 [hospital_node] Registering node 'hospital_B' ...
2026-03-07 10:01:30 [hospital_node] Registered as hospital_B (model v1)
2026-03-07 10:01:30 [hospital_node] === Round 1/3 ===
...
2026-03-07 10:01:45 [hospital_node] Update accepted (aggregated=True, model v2)
```

Once both nodes submit updates in the same round, the server aggregates automatically:
```
[aggregator] Aggregation complete — new model version: 2
```

---

## Step 5 — Run Tests

```powershell
cd D:\securederm-ai
.\venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```

---

## Docker Alternative

If you prefer Docker Compose:

```powershell
# Generate data first
python -m scripts.generate_mock_data

# Start everything
docker-compose up --build
```

This starts the aggregator + both hospital nodes automatically.

---

## Endpoints Reference

| Endpoint              | Method | Description                    |
|-----------------------|--------|--------------------------------|
| `/node/register`      | POST   | Register a hospital node       |
| `/training/update`    | POST   | Upload model weight updates    |
| `/model/latest`       | GET    | Download latest global model (node or admin token) |
| `/round/metrics`      | GET    | Per-round metrics (node or admin token) |
| `/status`             | GET    | Server health check            |

Notes:

- The aggregator binds to `AGGREGATOR_HOST` (default `127.0.0.1`). Set it to
  `0.0.0.0` only when nodes connect from other machines.
- `AGGREGATOR_ADMIN_TOKEN` (optional) lets an operator read metrics and the
  model without a node token. Leave it unset to disable admin access.
- The global model is saved to `checkpoints/global_model.pt` after every
  round and restored on startup (disable with `AGGREGATOR_PERSIST=false`).
- A restarted node whose `hospital_id` is still registered must set the
  `NODE_TOKEN` environment variable to its current token to re-register.
