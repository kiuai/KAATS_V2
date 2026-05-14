# KAATS Load Tests

k6-based load tests for the KAATS API.

## Prerequisites

Install k6: https://grafana.com/docs/k6/latest/set-up/install-k6/

```bash
# macOS
brew install k6

# Linux
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] \
  https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

## Running the tests

All scenarios target `http://localhost:8000` by default.
Override with `--env BASE_URL=<url>`.

```bash
# Health baseline (10 VUs, 60 s)
k6 run load-tests/k6/scenarios/01-health.js

# API smoke (1 VU, 1 iteration, all endpoints)
k6 run load-tests/k6/scenarios/02-api-smoke.js

# Sustained read load (30 VUs, 2 min ramp)
k6 run load-tests/k6/scenarios/03-api-load.js

# Against a staging environment
k6 run --env BASE_URL=https://api-staging.kaats.kiu.ai \
  load-tests/k6/scenarios/02-api-smoke.js
```

## Scenarios

| File | Purpose | VUs | Duration |
|---|---|---|---|
| `01-health.js` | Health SLO validation | 10 | 60 s |
| `02-api-smoke.js` | Post-deploy sanity check | 1 | 1 iteration |
| `03-api-load.js` | Sustained dashboard read load | 30 | ~2 min 45 s |

## Pass criteria

| Metric | Threshold |
|---|---|
| `http_req_failed` | < 1 % |
| `http_req_duration p(95)` | < 500 ms |
| `http_req_duration p(99)` | < 1 000 ms |
| `live_latency p(99)` | < 200 ms (health test only) |
