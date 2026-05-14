/**
 * k6 load test — API load scenario (sustained read traffic)
 *
 * Simulates 30 concurrent users reading the dashboard data for 2 minutes,
 * ramping up over 30 s and ramping down over 15 s.
 *
 * Endpoints exercised:
 *  - GET /health/live           (no auth, cheapest)
 *  - GET /api/v1/systems        (authenticated list)
 *  - GET /api/v1/usage/quota    (auth + DB aggregation)
 *  - GET /api/v1/agents         (auth + DB list)
 *
 * Pass criteria (p95 < 500 ms, p99 < 1000 ms, error rate < 1 %).
 *
 * Run:
 *   k6 run load-tests/k6/scenarios/03-api-load.js
 */

import http from 'k6/http'
import { check, sleep, group } from 'k6'
import { Rate } from 'k6/metrics'
import { BASE_URL, getDevToken, authHeaders } from '../config.js'

const errorRate = new Rate('errors')

export const options = {
  stages: [
    { duration: '30s', target: 30 },   // ramp up
    { duration: '120s', target: 30 },  // sustained
    { duration: '15s', target: 0 },    // ramp down
  ],
  thresholds: {
    errors: ['rate<0.01'],
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
  },
}

export function setup() {
  return getDevToken()
}

export default function (auth) {
  const h = authHeaders(auth.token, auth.companySlug)

  // Quick liveness ping
  group('liveness', () => {
    const r = http.get(`${BASE_URL}/health/live`)
    errorRate.add(!check(r, { 'live 200': (r) => r.status === 200 }))
  })

  // Authenticated reads (realistic dashboard load)
  group('dashboard reads', () => {
    const [sysList, quota, agentList] = http.batch([
      ['GET', `${BASE_URL}/api/v1/systems`, null, { headers: h }],
      ['GET', `${BASE_URL}/api/v1/usage/quota`, null, { headers: h }],
      ['GET', `${BASE_URL}/api/v1/agents`, null, { headers: h }],
    ])

    errorRate.add(
      !check(sysList,    { 'systems 200': (r) => r.status === 200 }) ||
      !check(quota,      { 'quota 200':   (r) => r.status === 200 }) ||
      !check(agentList,  { 'agents 200':  (r) => r.status === 200 })
    )
  })

  sleep(1)
}
