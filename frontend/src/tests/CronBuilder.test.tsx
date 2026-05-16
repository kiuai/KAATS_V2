/**
 * Tests for CronBuilder component and the describeSchedule utility.
 *
 * CronBuilder renders dropdowns for minute/hour/dom/month/dow and calls
 * onChange with the assembled cron string whenever any field changes.
 *
 * We also directly test describeSchedule() which is a pure function.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import CronBuilder from '@/components/CronBuilder'
import { describeSchedule } from '@/hooks/useSchedulePreview'

// ─────────────────────────────────────────────────────────────────────────────
// describeSchedule() — pure function tests (no React)
// ─────────────────────────────────────────────────────────────────────────────

describe('describeSchedule', () => {
  it('returns empty string for empty input', () => {
    expect(describeSchedule('')).toBe('')
  })

  it('describes every minute', () => {
    expect(describeSchedule('* * * * *')).toBe('Every minute')
  })

  it('describes every 15 minutes', () => {
    expect(describeSchedule('*/15 * * * *')).toBe('Every 15 minutes')
  })

  it('describes every 30 minutes', () => {
    expect(describeSchedule('*/30 * * * *')).toBe('Every 30 minutes')
  })

  it('describes daily at a specific time', () => {
    const result = describeSchedule('0 9 * * *')
    expect(result).toContain('09:00')
  })

  it('describes daily at midnight', () => {
    const result = describeSchedule('0 0 * * *')
    expect(result).toContain('00:00')
  })

  it('describes weekly on Monday', () => {
    const result = describeSchedule('0 9 * * 1')
    expect(result).toContain('Monday')
    expect(result).toContain('09:00')
  })

  it('describes weekly on Sunday', () => {
    const result = describeSchedule('0 8 * * 0')
    expect(result).toContain('Sunday')
  })

  it('describes monthly on day 1', () => {
    const result = describeSchedule('0 0 1 * *')
    expect(result).toContain('1')
  })

  it('returns fallback for expressions with wrong field count', () => {
    const result = describeSchedule('* * * *')
    expect(result).toContain('*')
  })

  it('describes hourly at minute N', () => {
    const result = describeSchedule('30 * * * *')
    expect(result).toContain('30')
    expect(result.toLowerCase()).toContain('hour')
  })

  it('returns a non-empty string for any valid-looking 5-part expression', () => {
    const exprs = ['0 2 * * *', '*/15 * * * *', '0 0 1 1 *', '0 9 * * 1-5']
    for (const e of exprs) {
      expect(describeSchedule(e).length).toBeGreaterThan(0)
    }
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// CronBuilder component tests
// ─────────────────────────────────────────────────────────────────────────────

describe('CronBuilder', () => {
  it('renders without crashing', () => {
    render(<CronBuilder value="0 9 * * 1" onChange={vi.fn()} />)
    // Should have select elements for time/schedule fields
    const selects = screen.getAllByRole('combobox')
    expect(selects.length).toBeGreaterThanOrEqual(2)
  })

  it('calls onChange on initial render', async () => {
    const onChange = vi.fn()
    render(<CronBuilder value="0 9 * * *" onChange={onChange} />)
    await waitFor(() => {
      expect(onChange).toHaveBeenCalled()
    })
  })

  it('displays a human-readable preview of the schedule', () => {
    render(<CronBuilder value="0 9 * * *" onChange={vi.fn()} />)
    // Preview text is rendered in a span; use getAllByText to handle multiple matches
    const matches = screen.getAllByText(/every day|09:00/i)
    expect(matches.length).toBeGreaterThanOrEqual(1)
  })

  it('updates cron string when hour is changed', async () => {
    const onChange = vi.fn()
    render(<CronBuilder value="0 9 * * *" onChange={onChange} />)

    // Find the hour select (labeled "HOUR" — label is uppercased via CSS but text is "Hour")
    const hourLabel = screen.getByText(/^hour$/i)
    const hourSelect = hourLabel.parentElement?.querySelector('select') as HTMLSelectElement
    expect(hourSelect).toBeTruthy()

    fireEvent.change(hourSelect, { target: { value: '14' } })

    await waitFor(() => {
      const calls = onChange.mock.calls
      const lastCall = calls[calls.length - 1][0] as string
      // New cron string should contain '14' for the hour
      expect(lastCall.split(' ')[1]).toBe('14')
    })
  })

  it('has a select for minute, hour, day of month, month, and day of week', () => {
    render(<CronBuilder value="0 0 * * *" onChange={vi.fn()} />)
    // Each field has a label — we expect at least 5 selects (one per field)
    const selects = screen.getAllByRole('combobox')
    expect(selects.length).toBeGreaterThanOrEqual(5)
  })

  it('parses and reflects the initial value correctly', () => {
    const onChange = vi.fn()
    render(<CronBuilder value="30 14 * * *" onChange={onChange} />)
    // The minute select should show 30
    const minuteSelects = screen.getAllByRole('combobox')
    const minuteSelect = minuteSelects[0] as HTMLSelectElement
    expect(minuteSelect.value).toBe('30')
  })
})
