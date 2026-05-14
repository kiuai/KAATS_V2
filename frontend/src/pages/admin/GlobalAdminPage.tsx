import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Plus, Pencil, X, Check } from 'lucide-react'
import { apiClient, errorMessage } from '@/services/api'
import { usePermission } from '@/hooks/usePermission'
import type { Enterprise } from '@/types'

// ── access denied ─────────────────────────────────────────────────────────

function AccessDenied() {
  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto">
      <div className="rounded-2xl bg-red-50 border border-red-200 p-10 text-center">
        <p className="text-lg font-semibold text-red-700 mb-2">Access Denied</p>
        <p className="text-sm text-red-600">
          This page requires global admin privileges.
        </p>
      </div>
    </div>
  )
}

// ── helpers ───────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// ── new enterprise modal ──────────────────────────────────────────────────

interface NewEnterpriseModalProps {
  onClose: () => void
}

interface NewEnterpriseForm {
  name: string
  slug: string
  azure_ad_tenant_id: string
}

function NewEnterpriseModal({ onClose }: NewEnterpriseModalProps) {
  const qc = useQueryClient()
  const [form, setForm] = useState<NewEnterpriseForm>({
    name: '',
    slug: '',
    azure_ad_tenant_id: '',
  })
  const [formError, setFormError] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: () =>
      apiClient
        .post<Enterprise>('/admin/enterprises', {
          name: form.name,
          slug: form.slug,
          azure_ad_tenant_id: form.azure_ad_tenant_id || null,
        })
        .then((r) => r.data),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['enterprises'] })
      onClose()
    },
    onError: (err) => setFormError(errorMessage(err)),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    createMutation.mutate()
  }

  const autoSlug = (name: string) =>
    name
      .toLowerCase()
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '')

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
        aria-labelledby="new-enterprise-title"
      >
        <button
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          onClick={onClose}
        >
          <X size={18} />
        </button>

        <h2 id="new-enterprise-title" className="text-base font-semibold text-gray-900 mb-5">
          New Enterprise
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="ent-name" className="block text-sm font-medium text-gray-700 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              id="ent-name"
              type="text"
              required
              value={form.name}
              onChange={(e) => {
                const name = e.target.value
                setForm((f) => ({ ...f, name, slug: autoSlug(name) }))
              }}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Acme Corp"
            />
          </div>

          <div>
            <label htmlFor="ent-slug" className="block text-sm font-medium text-gray-700 mb-1">
              Slug <span className="text-red-500">*</span>
            </label>
            <input
              id="ent-slug"
              type="text"
              required
              value={form.slug}
              onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="acme-corp"
            />
          </div>

          <div>
            <label htmlFor="ent-tenant" className="block text-sm font-medium text-gray-700 mb-1">
              Azure AD Tenant ID
            </label>
            <input
              id="ent-tenant"
              type="text"
              value={form.azure_ad_tenant_id}
              onChange={(e) => setForm((f) => ({ ...f, azure_ad_tenant_id: e.target.value }))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            />
          </div>

          {formError && <p className="text-sm text-red-600">{formError}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={createMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {createMutation.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── inline edit form ──────────────────────────────────────────────────────

interface InlineEditFormProps {
  enterprise: Enterprise
  onClose: () => void
}

function InlineEditForm({ enterprise, onClose }: InlineEditFormProps) {
  const qc = useQueryClient()
  const [name, setName] = useState(enterprise.name)
  const [azureTenantId, setAzureTenantId] = useState(
    enterprise.azure_ad_tenant_id ?? '',
  )
  const [isActive, setIsActive] = useState(enterprise.is_active)
  const [formError, setFormError] = useState<string | null>(null)

  const updateMutation = useMutation({
    mutationFn: () =>
      apiClient
        .patch<Enterprise>(`/admin/enterprises/${enterprise.id}`, {
          name,
          azure_ad_tenant_id: azureTenantId || null,
          is_active: isActive,
        })
        .then((r) => r.data),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['enterprises'] })
      onClose()
    },
    onError: (err) => setFormError(errorMessage(err)),
  })

  return (
    <tr className="bg-blue-50 border-b border-blue-100">
      <td colSpan={5} className="px-4 py-4">
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Azure Tenant ID
              </label>
              <input
                type="text"
                value={azureTenantId}
                onChange={(e) => setAzureTenantId(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Leave blank to clear"
              />
            </div>
            <div className="flex items-end gap-2">
              <button
                type="button"
                role="switch"
                aria-checked={isActive}
                onClick={() => setIsActive(!isActive)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  isActive ? 'bg-blue-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    isActive ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              <span className="text-sm text-gray-600">{isActive ? 'Active' : 'Inactive'}</span>
            </div>
          </div>

          {formError && <p className="text-xs text-red-600">{formError}</p>}

          <div className="flex gap-2">
            <button
              onClick={() => updateMutation.mutate()}
              disabled={updateMutation.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Check size={12} />
              {updateMutation.isPending ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={onClose}
              disabled={updateMutation.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <X size={12} />
              Cancel
            </button>
          </div>
        </div>
      </td>
    </tr>
  )
}

// ── skeleton ──────────────────────────────────────────────────────────────

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

// ── enterprise row ────────────────────────────────────────────────────────

interface EnterpriseRowProps {
  enterprise: Enterprise
}

function EnterpriseRow({ enterprise }: EnterpriseRowProps) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)

  const { data: detail } = useQuery<Enterprise>({
    queryKey: ['enterprise', enterprise.id],
    queryFn: () =>
      apiClient
        .get<Enterprise>(`/admin/enterprises/${enterprise.id}`)
        .then((r) => r.data),
    enabled: expanded,
  })

  return (
    <>
      <tr className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
        <td className="px-4 py-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1.5 font-medium text-gray-800 hover:text-blue-600"
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {enterprise.name}
          </button>
        </td>
        <td className="px-4 py-3 font-mono text-xs text-gray-500">{enterprise.slug}</td>
        <td className="px-4 py-3 font-mono text-xs text-gray-500">
          {enterprise.azure_ad_tenant_id ? (
            <span>{enterprise.azure_ad_tenant_id.slice(0, 8)}…</span>
          ) : (
            '—'
          )}
        </td>
        <td className="px-4 py-3">
          <span
            className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${
              enterprise.is_active
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-500'
            }`}
          >
            {enterprise.is_active ? 'Active' : 'Inactive'}
          </span>
        </td>
        <td className="px-4 py-3 text-gray-500 text-xs">{formatDate(enterprise.created_at)}</td>
        <td className="px-4 py-3">
          <button
            onClick={() => setEditing(true)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <Pencil size={11} />
            Edit
          </button>
        </td>
      </tr>

      {editing && (
        <InlineEditForm enterprise={enterprise} onClose={() => setEditing(false)} />
      )}

      {expanded && !editing && (
        <tr className="bg-gray-50 border-b border-gray-100">
          <td colSpan={6} className="px-6 py-3">
            <div className="text-sm text-gray-600 space-y-1">
              <p>
                <span className="font-medium text-gray-700">ID:</span>{' '}
                <span className="font-mono text-xs">{enterprise.id}</span>
              </p>
              {detail && (
                <>
                  <p>
                    <span className="font-medium text-gray-700">Updated:</span>{' '}
                    {formatDate(detail.updated_at)}
                  </p>
                  {detail.settings && Object.keys(detail.settings).length > 0 && (
                    <p>
                      <span className="font-medium text-gray-700">Settings:</span>{' '}
                      <span className="font-mono text-xs text-gray-500">
                        {JSON.stringify(detail.settings)}
                      </span>
                    </p>
                  )}
                </>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── page ──────────────────────────────────────────────────────────────────

function GlobalAdminContent() {
  const qc = useQueryClient()
  const [showNewModal, setShowNewModal] = useState(false)

  const {
    data: enterprises = [],
    isLoading,
    error,
  } = useQuery<Enterprise[]>({
    queryKey: ['enterprises'],
    queryFn: () =>
      apiClient.get<Enterprise[]>('/admin/enterprises').then((r) => r.data),
  })

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Global Admin</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage enterprises across the platform.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {errorMessage(error)}
        </div>
      )}

      {/* Enterprises section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-800">Enterprises</h2>
          <button
            onClick={() => setShowNewModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 transition-colors"
          >
            <Plus size={16} />
            New Enterprise
          </button>
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-left">
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Name
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Slug
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Azure Tenant ID
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Active
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Created
                </th>
                <th className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 4 }).map((_, i) => <TableRowSkeleton key={i} />)
              ) : enterprises.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-10 text-center text-sm text-gray-500"
                  >
                    No enterprises found.
                  </td>
                </tr>
              ) : (
                enterprises.map((ent) => (
                  <EnterpriseRow key={ent.id} enterprise={ent} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* New enterprise modal */}
      {showNewModal && (
        <NewEnterpriseModal onClose={() => setShowNewModal(false)} />
      )}
    </div>
  )
}

export default function GlobalAdminPage() {
  const allowed = usePermission('admin:global')
  if (!allowed) return <AccessDenied />
  return <GlobalAdminContent />
}
