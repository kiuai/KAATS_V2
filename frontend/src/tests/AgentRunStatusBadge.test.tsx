/**
 * Tests for the AgentRunStatusBadge component.
 *
 * Verifies correct label, CSS class behaviour, and pulse indicator for each
 * AgentRunStatus value.
 */
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import AgentRunStatusBadge from '@/components/AgentRunStatusBadge'
import type { AgentRunStatus } from '@/types'

// ─────────────────────────────────────────────────────────────────────────────

describe('AgentRunStatusBadge', () => {
  // ── Label rendering ────────────────────────────────────────────────────────

  const labelCases: Array<[AgentRunStatus, string]> = [
    ['pending',   'Pending'],
    ['running',   'Running'],
    ['completed', 'Completed'],
    ['failed',    'Failed'],
    ['timed_out', 'Timed Out'],
    ['cancelled', 'Cancelled'],
  ]

  it.each(labelCases)('renders the correct label for status "%s"', (status, expectedLabel) => {
    render(<AgentRunStatusBadge status={status} />)
    expect(screen.getByText(expectedLabel)).toBeInTheDocument()
  })

  // ── Pulse indicator ────────────────────────────────────────────────────────

  it('shows a pulse indicator dot when status is running', () => {
    const { container } = render(<AgentRunStatusBadge status="running" />)
    // The ping element has animate-ping class
    const pingDot = container.querySelector('.animate-ping')
    expect(pingDot).toBeInTheDocument()
  })

  it.each<AgentRunStatus>(['pending', 'completed', 'failed', 'timed_out', 'cancelled'])(
    'does not show a pulse dot for status "%s"',
    (status) => {
      const { container } = render(<AgentRunStatusBadge status={status} />)
      expect(container.querySelector('.animate-ping')).not.toBeInTheDocument()
    },
  )

  // ── Size prop ──────────────────────────────────────────────────────────────

  it('applies sm size classes when size="sm"', () => {
    const { container } = render(<AgentRunStatusBadge status="pending" size="sm" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('text-xs')
    expect(badge?.className).toContain('px-1.5')
  })

  it('applies md size classes when size="md" (default)', () => {
    const { container } = render(<AgentRunStatusBadge status="pending" size="md" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('px-2.5')
  })

  it('defaults to md size when size prop is omitted', () => {
    const { container } = render(<AgentRunStatusBadge status="pending" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('px-2.5')
  })

  // ── CSS colour classes ────────────────────────────────────────────────────

  it('uses green classes for completed status', () => {
    const { container } = render(<AgentRunStatusBadge status="completed" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('green')
  })

  it('uses red classes for failed status', () => {
    const { container } = render(<AgentRunStatusBadge status="failed" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('red')
  })

  it('uses blue classes for running status', () => {
    const { container } = render(<AgentRunStatusBadge status="running" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('blue')
  })

  it('uses orange classes for timed_out status', () => {
    const { container } = render(<AgentRunStatusBadge status="timed_out" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('orange')
  })

  // ── Renders as inline-flex span ───────────────────────────────────────────

  it('renders as a span element', () => {
    render(<AgentRunStatusBadge status="completed" />)
    const badge = screen.getByText('Completed').closest('span')
    expect(badge).toBeInTheDocument()
    expect(badge?.tagName.toLowerCase()).toBe('span')
  })
})
