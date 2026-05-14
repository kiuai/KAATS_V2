/**
 * Unit tests for the frontend RBAC permissions utility.
 *
 * These are pure-function tests; no React rendering required.
 */
import { describe, it, expect } from 'vitest'
import { hasPermission, hasAnyRole, ROLE_PERMISSIONS } from '@/auth/permissions'
import type { UserRoleEnum } from '@/types'

// ─────────────────────────────────────────────────────────────────────────────
// hasPermission()
// ─────────────────────────────────────────────────────────────────────────────

describe('hasPermission', () => {
  it('returns true when one of the user roles has the permission', () => {
    expect(hasPermission(['company_admin'], 'script:approve')).toBe(true)
  })

  it('returns false when none of the user roles have the permission', () => {
    expect(hasPermission(['bpo'], 'script:create')).toBe(false)
  })

  it('returns false for empty roles array', () => {
    expect(hasPermission([], 'req:read')).toBe(false)
  })

  it('returns true for global_admin on any permission', () => {
    const allPerms = Array.from(ROLE_PERMISSIONS['global_admin'] as Set<string>)
    for (const perm of allPerms) {
      expect(hasPermission(['global_admin'], perm as any)).toBe(true)
    }
  })

  it('returns true when at least one role in a multi-role array has the permission', () => {
    // bpo does not have agent:crawl, but qa does
    expect(hasPermission(['bpo', 'qa'], 'agent:crawl')).toBe(true)
  })

  it('returns false when none of multiple roles have the permission', () => {
    expect(hasPermission(['bpo', 'validation_tester'], 'agent:crawl')).toBe(false)
  })

  it('bpo can approve scripts', () => {
    expect(hasPermission(['bpo'], 'script:approve')).toBe(true)
  })

  it('bpo cannot create scripts', () => {
    expect(hasPermission(['bpo'], 'script:create')).toBe(false)
  })

  it('validation_tester cannot approve scripts', () => {
    expect(hasPermission(['validation_tester'], 'script:approve')).toBe(false)
  })

  it('validation_tester can create scripts', () => {
    expect(hasPermission(['validation_tester'], 'script:create')).toBe(true)
  })

  it('qa can run agents', () => {
    expect(hasPermission(['qa'], 'agent:crawl')).toBe(true)
    expect(hasPermission(['qa'], 'agent:generate')).toBe(true)
    expect(hasPermission(['qa'], 'agent:execute')).toBe(true)
  })

  it('qa cannot delete schedules', () => {
    expect(hasPermission(['qa'], 'schedule:delete')).toBe(false)
  })

  it('validation_lead cannot run crawl agent', () => {
    expect(hasPermission(['validation_lead'], 'agent:crawl')).toBe(false)
  })

  it('validation_lead can execute agents', () => {
    expect(hasPermission(['validation_lead'], 'agent:execute')).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// hasAnyRole()
// ─────────────────────────────────────────────────────────────────────────────

describe('hasAnyRole', () => {
  const userRoles: UserRoleEnum[] = ['qa', 'validation_tester']

  it('returns true when user has one of the required roles', () => {
    expect(hasAnyRole(userRoles, 'qa')).toBe(true)
  })

  it('returns true when user has multiple of the required roles', () => {
    expect(hasAnyRole(userRoles, 'qa', 'validation_tester')).toBe(true)
  })

  it('returns false when user has none of the required roles', () => {
    expect(hasAnyRole(userRoles, 'global_admin', 'company_admin')).toBe(false)
  })

  it('returns false for empty user roles', () => {
    expect(hasAnyRole([], 'qa')).toBe(false)
  })

  it('returns false for empty required roles', () => {
    expect(hasAnyRole(userRoles)).toBe(false)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// ROLE_PERMISSIONS map invariants
// ─────────────────────────────────────────────────────────────────────────────

describe('ROLE_PERMISSIONS', () => {
  const allRoles: UserRoleEnum[] = [
    'global_admin', 'enterprise_admin', 'company_admin',
    'system_manager', 'validation_lead', 'qa', 'validation_tester', 'bpo',
  ]

  it('covers all defined roles', () => {
    for (const role of allRoles) {
      expect(ROLE_PERMISSIONS).toHaveProperty(role)
    }
  })

  it('global_admin has admin:global', () => {
    expect((ROLE_PERMISSIONS['global_admin'] as Set<string>).has('admin:global')).toBe(true)
  })

  it('no role below enterprise_admin has admin:global', () => {
    const belowEnterprise: UserRoleEnum[] = [
      'company_admin', 'system_manager', 'validation_lead', 'qa', 'validation_tester', 'bpo',
    ]
    for (const role of belowEnterprise) {
      expect((ROLE_PERMISSIONS[role] as Set<string>).has('admin:global')).toBe(false)
    }
  })

  it('enterprise_admin does not have admin:global', () => {
    expect((ROLE_PERMISSIONS['enterprise_admin'] as Set<string>).has('admin:global')).toBe(false)
  })
})
