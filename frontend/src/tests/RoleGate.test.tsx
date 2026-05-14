/**
 * Tests for the RoleGate component.
 *
 * RoleGate renders children when the user has the required permission,
 * and the fallback (null by default) when they don't.
 *
 * We mock usePermission to control what the component "sees" without
 * needing a real Zustand store or auth context.
 */
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import RoleGate from '@/components/RoleGate'

// ── Mock usePermission ───────────────────────────────────────────────────────
vi.mock('@/hooks/usePermission', () => ({
  usePermission: vi.fn(),
}))

import { usePermission } from '@/hooks/usePermission'
const mockUsePermission = vi.mocked(usePermission)

// ─────────────────────────────────────────────────────────────────────────────

describe('RoleGate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders children when user has the permission', () => {
    mockUsePermission.mockReturnValue(true)
    render(
      <RoleGate permission="script:approve">
        <button>Approve</button>
      </RoleGate>,
    )
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument()
  })

  it('renders nothing by default when user lacks the permission', () => {
    mockUsePermission.mockReturnValue(false)
    const { container } = render(
      <RoleGate permission="admin:global">
        <button>Delete Everything</button>
      </RoleGate>,
    )
    expect(screen.queryByRole('button', { name: 'Delete Everything' })).not.toBeInTheDocument()
    expect(container).toBeEmptyDOMElement()
  })

  it('renders fallback when user lacks the permission and fallback is provided', () => {
    mockUsePermission.mockReturnValue(false)
    render(
      <RoleGate
        permission="admin:global"
        fallback={<span>Access denied</span>}
      >
        <button>Secret Action</button>
      </RoleGate>,
    )
    expect(screen.queryByRole('button', { name: 'Secret Action' })).not.toBeInTheDocument()
    expect(screen.getByText('Access denied')).toBeInTheDocument()
  })

  it('does not render fallback when user has the permission', () => {
    mockUsePermission.mockReturnValue(true)
    render(
      <RoleGate
        permission="req:create"
        fallback={<span>Access denied</span>}
      >
        <button>Create Requirement</button>
      </RoleGate>,
    )
    expect(screen.getByRole('button', { name: 'Create Requirement' })).toBeInTheDocument()
    expect(screen.queryByText('Access denied')).not.toBeInTheDocument()
  })

  it('passes the correct permission to usePermission', () => {
    mockUsePermission.mockReturnValue(true)
    render(
      <RoleGate permission="agent:crawl">
        <span>content</span>
      </RoleGate>,
    )
    expect(mockUsePermission).toHaveBeenCalledWith('agent:crawl')
  })

  it('renders multiple children when permitted', () => {
    mockUsePermission.mockReturnValue(true)
    render(
      <RoleGate permission="script:read">
        <li>Item 1</li>
        <li>Item 2</li>
        <li>Item 3</li>
      </RoleGate>,
    )
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
  })
})
