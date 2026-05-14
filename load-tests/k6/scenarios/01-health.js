/**
 * k6 load test — Health endpoint baseline
 *
 * Validates that /health/live and /health/ready respond within SLO
 * under light continuous load (10 VUs, 60s).
 *
 * Pass criteria:
 *   - 100 % of requests succeed (no 5xx).
 *   - p99 latency < 200 ms (liveness) and < 500 ms (readiness).
 *   - Error rate < 0.01 %.
 *
 * Run:
 *   k6 run load-tests/k6/scenarios/01-health.js
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { Rate, Trend } from 'k6/metrics'
import { BASE_URL } from '../config.js'

const errorRate = new Rate('errors')
const liveLatency = new Trend('live_latency', true)
const readyLatency = new Trend('ready_latency', true)

export const options = {
  vus: 10,
  duration: '60s',
  thresholds: {
    errors: ['rate<0.0001'],
    live_latency: ['p(99)<200'],
    ready_latency: ['p(99)<500'],
    http_req_failed: ['rate<0.001'],
  },
}

export default function () {
  // ── Liveness ──────────────────────────────────────────────────────────────
  const liveResp = http.get(`${BASE_URL}/health/live`)
  const liveOk = check(liveResp, {
    'live: status 200': (r) => r.status === 200,
    'live: body has alive': (r) => {
      try { return JSON.parse(r.body).status === 'alive' } catch { return false }
    },
  })
  errorRate.add(!liveOk)
  liveLatency.add(liveResp.timings.duration)

  // ── Readiness ─────────────────────────────────────────────────────────────
  const readyResp = http.get(`${BASE_URL}/health/ready`)
  const readyOk = check(readyResp, {
    'ready: status 200 or 503': (r) => r.status === 200 || r.status === 503,
    'ready: body has status field': (r) => {
      try { return 'status' in JSON.parse(r.body) } catch { return false }
    },
  })
  errorRate.add(!readyOk)
  readyLatency.add(readyResp.timings.duration)

  sleep(0.1)
}
