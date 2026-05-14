/**
 * k6 load test — API smoke (all major endpoints, single VU)
 *
 * Walks through the main API routes to verify all respond under normal
 * conditions.  Run this after every deployment as a quick sanity check.
 *
 * Not a stress test — 1 VU, 1 iteration per endpoint.
 *
 * Run:
 *   k6 run load-tests/k6/scenarios/02-api-smoke.js
 */

import http from 'k6/http'
import { check, group } from 'k6'
import { BASE_URL, getDevToken, authHeaders } from '../config.js'

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<3000'],
  },
}

export function setup() {
  return getDevToken()
}

export default function (auth) {
  const h = authHeaders(auth.token, auth.companySlug)

  // ── Health ────────────────────────────────────────────────────────────────
  group('health', () => {
    check(http.get(`${BASE_URL}/health/live`), {
      'live 200': (r) => r.status === 200,
    })
    check(http.get(`${BASE_URL}/health/ready`), {
      'ready 200|503': (r) => [200, 503].includes(r.status),
    })
  })

  // ── Auth ──────────────────────────────────────────────────────────────────
  group('auth', () => {
    check(http.get(`${BASE_URL}/api/v1/users/me`, { headers: h }), {
      'me 200': (r) => r.status === 200,
    })
  })

  // ── Tenants ───────────────────────────────────────────────────────────────
  group('tenants', () => {
    check(http.get(`${BASE_URL}/api/v1/tenants/companies`, { headers: h }), {
      'companies 200': (r) => r.status === 200,
    })
  })

  // ── Systems ───────────────────────────────────────────────────────────────
  group('systems', () => {
    check(http.get(`${BASE_URL}/api/v1/systems`, { headers: h }), {
      'systems list 200': (r) => r.status === 200,
    })
  })

  // ── Users ─────────────────────────────────────────────────────────────────
  group('users', () => {
    check(http.get(`${BASE_URL}/api/v1/users`, { headers: h }), {
      'users list 200': (r) => r.status === 200,
    })
  })

  // ── Agents ────────────────────────────────────────────────────────────────
  group('agents', () => {
    check(http.get(`${BASE_URL}/api/v1/agents`, { headers: h }), {
      'agents list 200': (r) => r.status === 200,
    })
  })

  // ── Usage & quota ─────────────────────────────────────────────────────────
  group('usage', () => {
    check(http.get(`${BASE_URL}/api/v1/usage/quota`, { headers: h }), {
      'quota 200': (r) => r.status === 200,
    })
    check(http.get(`${BASE_URL}/api/v1/usage/history`, { headers: h }), {
      'history 200': (r) => r.status === 200,
    })
  })

  // ── Onboarding ────────────────────────────────────────────────────────────
  group('onboarding', () => {
    check(http.get(`${BASE_URL}/api/v1/onboarding/status`, { headers: h }), {
      'onboarding status 200': (r) => r.status === 200,
    })
    check(http.get(`${BASE_URL}/api/v1/onboarding/invitations`, { headers: h }), {
      'invitations list 200': (r) => r.status === 200,
    })
  })

  // ── Reports ───────────────────────────────────────────────────────────────
  group('reports', () => {
    check(
      http.get(
        `${BASE_URL}/api/v1/reports/companies/${auth.companyId}/ai-usage`,
        { headers: h }
      ),
      { 'ai-usage report 200': (r) => r.status === 200 }
    )
  })
}
