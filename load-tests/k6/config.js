/**
 * Shared k6 configuration and helpers for KAATS load tests.
 *
 * Usage in a test script:
 *   import { BASE_URL, getDevToken, authHeaders } from './config.js'
 *
 * Run with:
 *   k6 run --env BASE_URL=http://localhost:8000 scenarios/01-health.js
 */

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000'

import http from 'k6/http'
import { check } from 'k6'

/**
 * Obtain a dev JWT from the KAATS API.
 * Called once in setup() so the token is shared across all VUs.
 *
 * @returns {string} Bearer token
 */
export function getDevToken(companySlug = '') {
  const resp = http.post(
    `${BASE_URL}/api/v1/auth/callback`,
    JSON.stringify({ code: 'dev', redirect_uri: 'http://localhost:5173' }),
    { headers: { 'Content-Type': 'application/json' } }
  )

  check(resp, {
    'dev login 200': (r) => r.status === 200,
  })

  if (resp.status !== 200) {
    throw new Error(`Dev login failed: ${resp.status} ${resp.body}`)
  }

  const data = JSON.parse(resp.body)
  return {
    token: data.access_token,
    companySlug: data.company?.slug ?? companySlug,
    companyId: data.company?.id ?? '',
  }
}

/**
 * Build headers for an authenticated API call.
 */
export function authHeaders(token, companySlug) {
  return {
    Authorization: `Bearer ${token}`,
    'X-Company-Slug': companySlug,
    'Content-Type': 'application/json',
  }
}
