import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { UserPlus, Trash2, Shield, X, ChevronDown, ChevronUp } from 'lucide-react'
import { apiClient, errorMessage } from '@/services/api'
import ConfirmDialog from '@/components/ConfirmDialog'
import { useAuthStore } from '@/store/authStore'
import type { User, UserRole, UserRoleEnum } from '@/types'

// ── helpers ───────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return 'Never'
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function initials(user: User): string {
  const name = user.display_name ?? user.email
  return name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
}

const ROLE_OPTIONS: UserRoleEnum[] = [
  'company_admin',
  'system_manager',
  'validation_lead',
  'qa',
  'validation_tester',
  'bpo',
]

const roleBadgeColor: Record<string, string> = {
  global_admin: 'bg-red-100 text-red-700',
  enterprise_admin: 'bg-orange-100 text-orange-700',
  company_admin: 'bg-purple-100 text-purple-700',
  system_manager: 'bg-blue-100 text-blue-700',
  validation_lead: 'bg-teal-100 text-teal-700',
  qa: 'bg-green-100 text-green-700',
  validation_tester: 'bg-cyan-100 text-cyan-700',
  bpo: 'bg-gray-100 text-gray-600',
}

// ── skeletons ─────────────────────────────────────────────────────────────

function TableRowSkeleton() {
  return (
    <tr className="animate-pulse border-b border-gray-50">
      {Array.from({ length: 5 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3 bg-gray-100 rounded w-full" />
        </td>
      ))}
    </tr>
  )
}

// ── invite modal ──────────────────────────────────────────────────────────

interface InviteModalProps {
  companyId: string
  onClose: () => void
}

function InviteModal({ companyId, onClose }: InviteModalProps) {
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState<UserRoleEnum>('qa')
  const [inviteError, setInviteError] = useState<string | null>(null)

  const inviteMutation = useMutation({
    mutationFn: () =>
      apiClient
        .post<User>('/users/invite', { email, display_name: displayName || null })
        .then((r) => r.data),
    onSuccess: async (user) => {
      // Assign initial role
      await apiClient.post(`/users/${user.id}/roles`, {
        role,
        company_id: companyId,
      })
      await qc.invalidateQueries({ queryKey: ['users'] })
      onClose()
    },
    onError: (err) => setInviteError(errorMessage(err)),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setInviteError(null)
    inviteMutation.mutate()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="invite-title"
      >
        <button
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          onClick={onClose}
        >
          <X size={18} />
        </button>

        <h2 id="invite-title" className="text-base font-semibold text-gray-900 mb-5">
          Invite User
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="invite-email" className="block text-sm font-medium text-gray-700 mb-1">
              Email <span className="text-red-500">*</span>
            </label>
            <input
              id="invite-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="user@example.com"
            />
          </div>

          <div>
            <label htmlFor="invite-name" className="block text-sm font-medium text-gray-700 mb-1">
              Display Name
            </label>
            <input
              id="invite-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Jane Smith"
            />
          </div>

          <div>
            <label htmlFor="invite-role" className="block text-sm font-medium text-gray-700 mb-1">
              Initial Role
            </label>
            <select
              id="invite-role"
              value={role}
              onChange={(e) => setRole(e.target.value as UserRoleEnum)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          {inviteError && (
            <p className="text-sm text-red-600">{inviteError}</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={inviteMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={inviteMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {inviteMutation.isPending ? 'Inviting…' : 'Send Invite'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── add role form ─────────────────────────────────────────────────────────

interface AddRoleFormProps {
  userId: string
  onDone: () => void
}

function AddRoleForm({ userId, onDone }: AddRoleFormProps) {
  const qc = useQueryClient()
  const [role, setRole] = useState<UserRoleEnum>('qa')
  const [systemId, setSystemId] = useState('')
  const [businessDomain, setBusinessDomain] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const addMutation = useMutation({
    mutationFn: () =>
      apiClient
        .post(`/users/${userId}/roles`, {
          role,
          system_id: systemId || null,
          business_domain: businessDomain || null,
          expires_at: expiresAt || null,
        })
        .then((r) => r.data),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['user-roles', userId] })
      onDone()
    },
    onError: (err) => setFormError(errorMessage(err)),
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        setFormError(null)
        addMutation.mutate()
      }}
      className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3"
    >
      <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
        Add Role
      </p>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as UserRoleEnum)}
            className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {ROLE_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>

        {role === 'system_manager' && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">System ID</label>
            <input
              type="text"
              value={systemId}
              onChange={(e) => setSystemId(e.target.value)}
              placeholder="System UUID"
              className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}

        {role === 'bpo' && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Business Domain</label>
            <input
              type="text"
              value={businessDomain}
              onChange={(e) => setBusinessDomain(e.target.value)}
              placeholder="e.g. Finance"
              className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Expires At</label>
          <input
            type="datetime-local"
            value={expiresAt}
            onChange={(e) => setExpiresAt(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {formError && <p className="text-xs text-red-600">{formError}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={addMutation.isPending}
          className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {addMutation.isPending ? 'Adding…' : 'Add Role'}
        </button>
        <button
          type="button"
          onClick={onDone}
          disabled={addMutation.isPending}
          className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

// ── roles panel drawer ────────────────────────────────────────────────────

interface RolesPanelProps {
  user: User
  onClose: () => void
}

function RolesPanel({ user, onClose }: RolesPanelProps) {
  const qc = useQueryClient()
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)

  const { data: roles = [], isLoading } = useQuery<UserRole[]>({
    queryKey: ['user-roles', user.id],
    queryFn: () =>
      apiClient.get<UserRole[]>(`/users/${user.id}/roles`).then((r) => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (roleId: string) =>
      apiClient.delete(`/users/${user.id}/roles/${roleId}`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['user-roles', user.id] })
      setDeleteTargetId(null)
    },
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-end bg-black/30"
      onClick={onClose}
    >
      <div
        className="relative bg-white w-full max-w-md h-full overflow-y-auto shadow-2xl p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            Roles — {user.display_name ?? user.email}
          </h2>
          <button
            className="text-gray-400 hover:text-gray-600"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-10 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : roles.length === 0 ? (
          <p className="text-sm text-gray-500">No roles assigned.</p>
        ) : (
          <div className="space-y-2">
            {roles.map((r) => (
              <div
                key={r.id}
                className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded-xl px-4 py-2"
              >
                <div>
                  <span
                    className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${roleBadgeColor[r.role] ?? 'bg-gray-100 text-gray-600'}`}
                  >
                    {r.role.replace(/_/g, ' ')}
                  </span>
                  {r.expires_at && (
                    <p className="text-xs text-gray-400 mt-0.5">
                      Expires {formatDate(r.expires_at)}
                    </p>
                  )}
                </div>
                <button
                  className="text-red-400 hover:text-red-600"
                  title="Remove role"
                  onClick={() => setDeleteTargetId(r.id)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        {showAddForm ? (
          <AddRoleForm userId={user.id} onDone={() => setShowAddForm(false)} />
        ) : (
          <button
            onClick={() => setShowAddForm(true)}
            className="w-full py-2 text-sm font-medium text-blue-600 border border-blue-200 rounded-xl hover:bg-blue-50 transition-colors"
          >
            + Add Role
          </button>
        )}

        <ConfirmDialog
          open={deleteTargetId !== null}
          title="Remove Role"
          description="Are you sure you want to remove this role from the user?"
          confirmLabel="Remove"
          destructive
          loading={deleteMutation.isPending}
          onConfirm={() => {
            if (deleteTargetId) deleteMutation.mutate(deleteTargetId)
          }}
          onCancel={() => setDeleteTargetId(null)}
        />
      </div>
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────

export default function UsersPage() {
  const qc = useQueryClient()
  const currentUser = useAuthStore((s) => s.user)
  const companyId = useAuthStore((s) => s.currentCompany?.id)

  const [showInvite, setShowInvite] = useState(false)
  const [rolesUser, setRolesUser] = useState<User | null>(null)
  const [deactivateTarget, setDeactivateTarget] = useState<User | null>(null)
  const [expandedRoles, setExpandedRoles] = useState<Set<string>>(new Set())

  const {
    data: users = [],
    isLoading,
    error,
  } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => apiClient.get<User[]>('/users').then((r) => r.data),
  })

  // Per-user roles (lazy loaded for role chips display)
  const userRolesQueries = useQuery<Record<string, UserRole[]>>({
    queryKey: ['users-all-roles'],
    queryFn: async () => {
      const results: Record<string, UserRole[]> = {}
      await Promise.all(
        users.map(async (u) => {
          try {
            const r = await apiClient.get<UserRole[]>(`/users/${u.id}/roles`)
            results[u.id] = r.data
          } catch {
            results[u.id] = []
          }
        }),
      )
      return results
    },
    enabled: users.length > 0,
  })

  const deactivateMutation = useMutation({
    mutationFn: (userId: string) => apiClient.delete(`/users/${userId}`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['users'] })
      setDeactivateTarget(null)
    },
  })

  const toggleExpanded = (id: string) => {
    setExpandedRoles((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Users</h1>
        <button
          onClick={() => setShowInvite(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 transition-colors"
        >
          <UserPlus size={16} />
          Invite User
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50 text-left">
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                User
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Status
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Roles
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Last Login
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => <TableRowSkeleton key={i} />)
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-500">
                  No users found.
                </td>
              </tr>
            ) : (
              users.map((user) => {
                const userRoles = userRolesQueries.data?.[user.id] ?? []
                const isExpanded = expandedRoles.has(user.id)
                const visibleRoles = isExpanded ? userRoles : userRoles.slice(0, 3)

                return (
                  <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                    {/* User */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-700 shrink-0">
                          {initials(user)}
                        </div>
                        <div>
                          <p className="font-medium text-gray-800">
                            {user.display_name ?? '—'}
                          </p>
                          <p className="text-xs text-gray-500">{user.email}</p>
                        </div>
                      </div>
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          user.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>

                    {/* Roles */}
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {visibleRoles.map((r) => (
                          <span
                            key={r.id}
                            className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${roleBadgeColor[r.role] ?? 'bg-gray-100 text-gray-600'}`}
                          >
                            {r.role.replace(/_/g, ' ')}
                          </span>
                        ))}
                        {userRoles.length > 3 && (
                          <button
                            onClick={() => toggleExpanded(user.id)}
                            className="inline-flex items-center gap-0.5 text-xs text-blue-600 hover:underline"
                          >
                            {isExpanded ? (
                              <>
                                <ChevronUp size={12} /> less
                              </>
                            ) : (
                              <>
                                <ChevronDown size={12} /> +{userRoles.length - 3} more
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </td>

                    {/* Last Login */}
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {formatDate(user.last_login_at)}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setRolesUser(user)}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
                        >
                          <Shield size={12} />
                          Roles
                        </button>
                        {user.is_active && user.id !== currentUser?.id && (
                          <button
                            onClick={() => setDeactivateTarget(user)}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50"
                          >
                            <Trash2 size={12} />
                            Deactivate
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Invite modal */}
      {showInvite && companyId && (
        <InviteModal companyId={companyId} onClose={() => setShowInvite(false)} />
      )}

      {/* Roles drawer */}
      {rolesUser && (
        <RolesPanel user={rolesUser} onClose={() => setRolesUser(null)} />
      )}

      {/* Deactivate confirm */}
      <ConfirmDialog
        open={deactivateTarget !== null}
        title="Deactivate User"
        description={`Are you sure you want to deactivate ${deactivateTarget?.display_name ?? deactivateTarget?.email}? They will no longer be able to log in.`}
        confirmLabel="Deactivate"
        destructive
        loading={deactivateMutation.isPending}
        onConfirm={() => {
          if (deactivateTarget) deactivateMutation.mutate(deactivateTarget.id)
        }}
        onCancel={() => setDeactivateTarget(null)}
      />
    </div>
  )
}
