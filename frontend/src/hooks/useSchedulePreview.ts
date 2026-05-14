/**
 * Returns a human-readable description for a cron expression.
 * Handles simple cases without an external library.
 */
export function useSchedulePreview(cronExpr: string): string {
  return describeSchedule(cronExpr)
}

export function describeSchedule(cron: string): string {
  if (!cron || cron.trim() === '') return ''

  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) return `Custom schedule: ${cron}`

  const [minute, hour, dom, month, dow] = parts

  const allWildcard = (v: string) => v === '*'

  // Every minute
  if (allWildcard(minute) && allWildcard(hour) && allWildcard(dom) && allWildcard(month) && allWildcard(dow)) {
    return 'Every minute'
  }

  // Every N minutes
  if (minute.startsWith('*/') && allWildcard(hour) && allWildcard(dom) && allWildcard(month) && allWildcard(dow)) {
    return `Every ${minute.slice(2)} minutes`
  }

  // Hourly at minute N
  if (!allWildcard(minute) && allWildcard(hour) && allWildcard(dom) && allWildcard(month) && allWildcard(dow)) {
    return `Every hour at minute ${minute}`
  }

  const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
  const MONTHS = ['', 'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December']

  const timeStr = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')} UTC`

  // Daily
  if (allWildcard(dom) && allWildcard(month) && allWildcard(dow)) {
    return `Every day at ${timeStr}`
  }

  // Specific days of week
  if (allWildcard(dom) && allWildcard(month) && !allWildcard(dow)) {
    const days = dow.split(',').map((d) => DAYS[Number(d)] ?? d).join(', ')
    return `Every ${days} at ${timeStr}`
  }

  // Day of month
  if (!allWildcard(dom) && allWildcard(month) && allWildcard(dow)) {
    return `Monthly on day ${dom} at ${timeStr}`
  }

  // Monthly in specific month
  if (!allWildcard(month) && !allWildcard(dom) && allWildcard(dow)) {
    const monthName = MONTHS[Number(month)] ?? month
    return `${monthName} ${dom} at ${timeStr}`
  }

  return `${cron}`
}
