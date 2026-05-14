import type { UserRoleEnum } from '@/types'

// Mirror of backend Permission enum
export type Permission =
  | 'enterprise:read' | 'enterprise:manage'
  | 'company:read' | 'company:manage'
  | 'user:read' | 'user:invite' | 'user:update' | 'user:deactivate' | 'user:assign_role'
  | 'system:read' | 'system:create' | 'system:update' | 'system:delete' | 'system:manage_own'
  | 'req:read' | 'req:create' | 'req:update' | 'req:delete' | 'req:import'
  | 'script:read' | 'script:create' | 'script:update' | 'script:delete' | 'script:approve' | 'script:export'
  | 'cycle:read' | 'cycle:create' | 'cycle:update' | 'cycle:delete'
  | 'assignment:create' | 'assignment:update'
  | 'result:read' | 'result:create'
  | 'agent:crawl' | 'agent:generate' | 'agent:execute'
  | 'schedule:read' | 'schedule:create' | 'schedule:update' | 'schedule:delete'
  | 'evidence:read' | 'evidence:export'
  | 'report:read' | 'report:export'
  | 'admin:global' | 'admin:enterprise' | 'admin:company'
  | 'audit:log_read' | 'ai:usage_read'

const ALL_PERMISSIONS = new Set<Permission>([
  'enterprise:read', 'enterprise:manage',
  'company:read', 'company:manage',
  'user:read', 'user:invite', 'user:update', 'user:deactivate', 'user:assign_role',
  'system:read', 'system:create', 'system:update', 'system:delete', 'system:manage_own',
  'req:read', 'req:create', 'req:update', 'req:delete', 'req:import',
  'script:read', 'script:create', 'script:update', 'script:delete', 'script:approve', 'script:export',
  'cycle:read', 'cycle:create', 'cycle:update', 'cycle:delete',
  'assignment:create', 'assignment:update',
  'result:read', 'result:create',
  'agent:crawl', 'agent:generate', 'agent:execute',
  'schedule:read', 'schedule:create', 'schedule:update', 'schedule:delete',
  'evidence:read', 'evidence:export',
  'report:read', 'report:export',
  'admin:global', 'admin:enterprise', 'admin:company',
  'audit:log_read', 'ai:usage_read',
])

const ROLE_PERMISSIONS: Record<UserRoleEnum, Set<Permission>> = {
  global_admin: ALL_PERMISSIONS,

  enterprise_admin: new Set([...ALL_PERMISSIONS].filter((p) => p !== 'admin:global')),

  company_admin: new Set<Permission>([
    'company:read', 'company:manage',
    'user:read', 'user:invite', 'user:update', 'user:deactivate', 'user:assign_role',
    'system:read', 'system:create', 'system:update', 'system:delete',
    'req:read', 'req:create', 'req:update', 'req:delete', 'req:import',
    'script:read', 'script:create', 'script:update', 'script:delete', 'script:approve', 'script:export',
    'cycle:read', 'cycle:create', 'cycle:update', 'cycle:delete',
    'assignment:create', 'assignment:update',
    'result:read', 'result:create',
    'agent:crawl', 'agent:generate', 'agent:execute',
    'schedule:read', 'schedule:create', 'schedule:update', 'schedule:delete',
    'evidence:read', 'evidence:export',
    'report:read', 'report:export',
    'admin:company', 'ai:usage_read',
  ]),

  system_manager: new Set<Permission>([
    'system:read', 'system:manage_own',
    'req:read', 'req:create', 'req:update', 'req:delete', 'req:import',
    'script:read', 'script:create', 'script:update', 'script:approve', 'script:export',
    'cycle:read', 'cycle:create', 'assignment:create',
    'result:read',
    'agent:crawl', 'agent:generate', 'agent:execute',
    'schedule:read', 'schedule:create', 'schedule:update', 'schedule:delete',
    'evidence:read',
    'report:read', 'report:export',
    'user:read', 'ai:usage_read',
  ]),

  validation_lead: new Set<Permission>([
    'cycle:read', 'cycle:create', 'cycle:update', 'cycle:delete',
    'assignment:create', 'assignment:update',
    'script:read', 'script:approve', 'script:export',
    'req:read',
    'result:read',
    'report:read', 'report:export',
    'evidence:read',
    'agent:execute',
    'user:read',
  ]),

  qa: new Set<Permission>([
    'result:read', 'result:create',
    'assignment:update',
    'script:read',
    'req:read',
    'evidence:read',
    'report:read',
    'user:read',
    'agent:crawl', 'agent:generate', 'agent:execute',
  ]),

  validation_tester: new Set<Permission>([
    'script:read', 'script:create', 'script:update',
    'req:read',
    'result:create',
    'assignment:update',
    'evidence:read',
    'user:read',
  ]),

  bpo: new Set<Permission>([
    'req:read',
    'script:read', 'script:approve',
    'result:read',
    'report:read',
    'evidence:read',
    'user:read',
  ]),
}

export function hasPermission(roles: UserRoleEnum[], permission: Permission): boolean {
  return roles.some((role) => ROLE_PERMISSIONS[role]?.has(permission) ?? false)
}

export function hasAnyRole(userRoles: UserRoleEnum[], ...requiredRoles: UserRoleEnum[]): boolean {
  return requiredRoles.some((r) => userRoles.includes(r))
}

export { ROLE_PERMISSIONS }
