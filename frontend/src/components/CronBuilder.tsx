import { useState, useEffect } from 'react'
import { describeSchedule } from '@/hooks/useSchedulePreview'

interface Props {
  value: string
  onChange: (cron: string) => void
}

const MINUTES = Array.from({ length: 60 }, (_, i) => String(i))
const HOURS = Array.from({ length: 24 }, (_, i) => String(i))
const DAYS = Array.from({ length: 31 }, (_, i) => String(i + 1))
const MONTHS = [
  { v: '*', l: 'Every month' },
  { v: '1', l: 'January' }, { v: '2', l: 'February' }, { v: '3', l: 'March' },
  { v: '4', l: 'April' }, { v: '5', l: 'May' }, { v: '6', l: 'June' },
  { v: '7', l: 'July' }, { v: '8', l: 'August' }, { v: '9', l: 'September' },
  { v: '10', l: 'October' }, { v: '11', l: 'November' }, { v: '12', l: 'December' },
]
const DOW = [
  { v: '*', l: 'Every day' },
  { v: '1', l: 'Monday' }, { v: '2', l: 'Tuesday' }, { v: '3', l: 'Wednesday' },
  { v: '4', l: 'Thursday' }, { v: '5', l: 'Friday' },
  { v: '6', l: 'Saturday' }, { v: '0', l: 'Sunday' },
]

function parseCron(cron: string) {
  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) return { minute: '0', hour: '0', dom: '*', month: '*', dow: '*' }
  const [minute, hour, dom, month, dow] = parts
  return { minute, hour, dom, month, dow }
}

export default function CronBuilder({ value, onChange }: Props) {
  const parsed = parseCron(value)
  const [minute, setMinute] = useState(parsed.minute)
  const [hour, setHour] = useState(parsed.hour)
  const [dom, setDom] = useState(parsed.dom)
  const [month, setMonth] = useState(parsed.month)
  const [dow, setDow] = useState(parsed.dow)

  // Update parent whenever any field changes
  useEffect(() => {
    onChange(`${minute} ${hour} ${dom} ${month} ${dow}`)
  }, [minute, hour, dom, month, dow, onChange])

  const cronStr = `${minute} ${hour} ${dom} ${month} ${dow}`
  const preview = describeSchedule(cronStr)

  const sel = (
    val: string,
    onChangeFn: (v: string) => void,
    options: { v: string; l: string }[],
    label: string,
  ) => (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</label>
      <select
        value={val}
        onChange={(e) => onChangeFn(e.target.value)}
        className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {options.map((o) => (
          <option key={o.v} value={o.v}>{o.l}</option>
        ))}
      </select>
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {sel(minute, setMinute, [{ v: '*', l: 'Every minute' }, ...MINUTES.map((m) => ({ v: m, l: m }))], 'Minute')}
        {sel(hour, setHour, [{ v: '*', l: 'Every hour' }, ...HOURS.map((h) => ({ v: h, l: h }))], 'Hour')}
        {sel(dom, setDom, [{ v: '*', l: 'Every day' }, ...DAYS.map((d) => ({ v: d, l: d }))], 'Day')}
        {sel(month, setMonth, MONTHS, 'Month')}
        {sel(dow, setDow, DOW, 'Weekday')}
      </div>

      <div className="flex items-center gap-3 px-4 py-3 bg-blue-50 border border-blue-200 rounded-xl">
        <span className="font-mono text-sm text-blue-700 font-medium">{cronStr}</span>
        <span className="text-gray-400">·</span>
        <span className="text-sm text-blue-700">{preview}</span>
      </div>

      {/* Raw input override */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-500">Custom cron expression</label>
        <input
          type="text"
          value={cronStr}
          onChange={(e) => {
            const p = parseCron(e.target.value)
            setMinute(p.minute)
            setHour(p.hour)
            setDom(p.dom)
            setMonth(p.month)
            setDow(p.dow)
          }}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="* * * * *"
        />
      </div>
    </div>
  )
}
