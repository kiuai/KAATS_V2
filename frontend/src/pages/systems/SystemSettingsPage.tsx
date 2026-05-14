import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient, errorMessage } from '@/services/api'
import RoleGate from '@/components/RoleGate'
import ConfirmDialog from '@/components/ConfirmDialog'
import type { System, User, UserRole } from '@/types'

// ── types ─────────────────────────────────────────────────────────────────

type SystemType = 'web' | 'sap_fiori' | 'api' | 'other'

interface SystemPatchBody {
  name: string
  description: string
  base_url: string
  system_type: SystemType
  is_active: boolean
}

interface TeamMember {
  user: User
  role: UserRole
  business_domain: string | null
}

// ── helpers ───────────────────────────────────────────────────────────────

function toFormState(system: System): SystemPatchBody {
  return {
    name: system.name,
    description: system.description ?? '',
    base_url: system.base_url ?? '',
    system_type: (system.system_type as SystemType) ?? 'web',
    is_active: system.is_active,
  }
}

// ── skeleton ──────────────────────────────────────────────────────────────

function FormSkeleton() {
  return (
    <div className="animate-pulse space-y-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i}>
          <div className="h-3 w-24 bg-gray-200 rounded mb-1.5" />
          <div className="h-10 bg-gray-100 rounded-lg" />
        </div>
      ))}
    </div>
  )
}

// ── component ─────────────────────────────────────────────────────────────

export default function SystemSettingsPage() {
  const { systemId } = useParams<{ systemId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [form, setForm] = useState<SystemPatchBody | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [assignUserId, setAssignUserId] = useState<string>('')
  const [assignError, setAssignError] = useState<string | null>(null)
  const [assignSuccess, setAssignSuccess] = useState<string | null>(null)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)

  // ── fetch system ──────────────────────────────────────────────
  const { data: system, isLoading, error } = useQuery<System>({
    queryKey: ['systems', systemId],
    queryFn: () =>
      apiClient.get<System>(`/systems/${systemId}`).then((r) => r.data),
    enabled: !!systemId,
  })

  // ── fetch team (for current manager) ─────────────────────────
  const { data: team = [] } = useQuery<TeamMember[]>({
    queryKey: ['systems', systemId, 'team'],
    queryFn: () =>
      apiClient.get<TeamMember[]>(`/systems/${systemId}/team`).then((r) => r.data),
    enabled: !!systemId,
  })

  // ── fetch users (for assign dropdown) ────────────────────────
  const { data: users = [] } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => apiClient.get<User[]>('/users').then((r) => r.data),
  })

  // Populate form when system loads
  useEffect(() => {
    if (system && form === null) {
      setForm(toFormState(system))
    }
  }, [system, form])

  // ── mutations ─────────────────────────────────────────────────
  const patchMutation = useMutation({
    mutationFn: (body: SystemPatchBody) =>
      apiClient.patch<System>(`/systems/${systemId}`, body).then((r) => r.data),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ['systems'] })
      qc.setQueryData(['systems', systemId], updated)
      setSuccessMsg('Settings saved successfully.')
      setFormError(null)
      setTimeout(() => setSuccessMsg(null), 4000)
    },
    onError: (err) => {
      setFormError(errorMessage(err))
      setSuccessMsg(null)
    },
  })

  const assignMutation = useMutation({
    mutationFn: (userId: string) =>
      apiClient
        .post<System>(`/systems/${systemId}/assign-manager`, { user_id: userId })
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['systems', systemId, 'team'] })
      qc.invalidateQueries({ queryKey: ['systems', systemId] })
      setAssignSuccess('Manager assigned successfully.')
      setAssignError(null)
      setAssignUserId('')
      setTimeout(() => setAssignSuccess(null), 4000)
    },
    onError: (err) => {
      setAssignError(errorMessage(err))
      setAssignSuccess(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () =>
      apiClient.delete(`/systems/${systemId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['systems'] })
      navigate('/systems')
    },
  })

  // ── form helpers ──────────────────────────────────────────────
  function setField<K extends keyof SystemPatchBody>(key: K, value: SystemPatchBody[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form || !form.name.trim()) return
    patchMutation.mutate(form)
  }

  // Current manager from team
  const currentManager = team.find((m) => m.role.role === 'system_manager')

  // ── render ────────────────────────────────────────────────────
  if (!systemId) {
    return <div className="p-8 text-sm text-red-600">Invalid system URL.</div>
  }

  if (error) {
    return <div className="p-8 text-sm text-red-600">{errorMessage(error)}</div>
  }

  return (
    <div className="p-6 lg:p-8 max-w-2xl mx-auto space-y-10">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">System Settings</h1>
        {system && (
          <p className="mt-1 text-sm text-gray-500">{system.name}</p>
        )}
      </div>

      {/* ── Edit form ───────────────────────────────────────────── */}
      <section className="bg-white border border-gray-200 rounded-2xl p-6">
        <h2 className="text-base font-semibold text-gray-900 mb-5">General</h2>

        {isLoading || !form ? (
          <FormSkeleton />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {successMsg && (
              <div className="rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
                {successMsg}
              </div>
            )}
            {formError && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {formError}
              </div>
            )}

            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={form.description}
                onChange={(e) => setField('description', e.target.value)}
                rows={3}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
            </div>

            {/* Base URL */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Base URL
              </label>
              <input
                type="url"
                value={form.base_url}
                onChange={(e) => setField('base_url', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="https://example.com"
              />
            </div>

            {/* System type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                System Type
              </label>
              <select
                value={form.system_type}
                onChange={(e) => setField('system_type', e.target.value as SystemType)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="web">Web</option>
                <option value="sap_fiori">SAP Fiori</option>
                <option value="api">API</option>
                <option value="other">Other</option>
              </select>
            </div>

            {/* Active toggle */}
            <div className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-gray-700">Active</p>
                <p className="text-xs text-gray-400">
                  Inactive systems are hidden from agent runs and schedules.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setField('is_active', !form.is_active)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                  form.is_active ? 'bg-blue-600' : 'bg-gray-200'
                }`}
                role="switch"
                aria-checked={form.is_active}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    form.is_active ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={patchMutation.isPending}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-xl disabled:opacity-50 transition-colors"
              >
                {patchMutation.isPending ? 'Saving…' : 'Save Changes'}
              </button>
            </div>
          </form>
        )}
      </section>

      {/* ── Assign Manager ──────────────────────────────────────── */}
      <RoleGate permission="system:update">
        <section className="bg-white border border-gray-200 rounded-2xl p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-1">
            System Manager
          </h2>

          {currentManager && (
            <p className="text-sm text-gray-500 mb-4">
              Current manager:{' '}
              <span className="font-medium text-gray-800">
                {currentManager.user.display_name ?? currentManager.user.email}
              </span>{' '}
              <span className="text-gray-400">({currentManager.user.email})</span>
            </p>
          )}

          {assignSuccess && (
            <div className="mb-3 rounded-lg bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
              {assignSuccess}
            </div>
          )}
          {assignError && (
            <div className="mb-3 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {assignError}
            </div>
          )}

          <div className="flex gap-3">
            <select
              value={assignUserId}
              onChange={(e) => setAssignUserId(e.target.value)}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="">Select a user…</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name ? `${u.display_name} (${u.email})` : u.email}
                </option>
              ))}
            </select>
            <button
              onClick={() => assignUserId && assignMutation.mutate(assignUserId)}
              disabled={!assignUserId || assignMutation.isPending}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-xl disabled:opacity-50 transition-colors"
            >
              {assignMutation.isPending ? 'Assigning…' : 'Assign'}
            </button>
          </div>
        </section>
      </RoleGate>

      {/* ── Danger Zone ─────────────────────────────────────────── */}
      <RoleGate permission="system:delete">
        <section className="border border-red-200 rounded-2xl p-6">
          <h2 className="text-base font-semibold text-red-700 mb-1">
            Danger Zone
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Permanently delete this system and all associated data. This action
            cannot be undone.
          </p>
          <button
            onClick={() => setShowDeleteDialog(true)}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-xl transition-colors"
          >
            Delete System
          </button>
        </section>
      </RoleGate>

      {/* ── Delete confirm ───────────────────────────────────────── */}
      <ConfirmDialog
        open={showDeleteDialog}
        title="Delete System"
        description={`Are you sure you want to permanently delete "${system?.name ?? 'this system'}"? All requirements, scripts, cycles, and agent runs associated with it will be removed.`}
        confirmLabel="Delete"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setShowDeleteDialog(false)}
      />
    </div>
  )
}
