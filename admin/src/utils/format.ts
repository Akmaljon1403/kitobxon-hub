const MONTHS = [
  'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
  'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
]
const WEEKDAYS = ['yakshanba', 'dushanba', 'seshanba', 'chorshanba', 'payshanba', 'juma', 'shanba']
const CLUB_TIME_ZONE = 'Asia/Tashkent'

interface Parts {
  year: number
  month: number
  day: number
  weekday: number
  hour: string
  minute: string
}

/** Calendar parts of a timestamp in the club's time zone (Tashkent), independent of the phone's settings. */
function parts(value: string): Parts | null {
  const date = value.length === 10 ? new Date(`${value}T00:00:00+05:00`) : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  const formatted = new Intl.DateTimeFormat('en-GB', {
    timeZone: CLUB_TIME_ZONE,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const get = (type: string) => formatted.find((part) => part.type === type)?.value ?? ''
  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  return {
    year: Number(get('year')),
    month: Number(get('month')) - 1,
    day: Number(get('day')),
    weekday: weekdays.indexOf(get('weekday')),
    hour: get('hour'),
    minute: get('minute'),
  }
}

/** "15-oktabr" (current year) or "15-oktabr, 2027". Accepts "2026-10-15" or ISO timestamps. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const p = parts(value)
  if (!p) return '—'
  const base = `${p.day}-${MONTHS[p.month]}`
  return p.year === new Date().getFullYear() ? base : `${base}, ${p.year}`
}

export function formatTime(value: string | null | undefined): string {
  const p = value ? parts(value) : null
  return p ? `${p.hour}:${p.minute}` : '—'
}

/** "Payshanba, 15-oktabr · 15:00" */
export function formatEventDate(value: string): string {
  const p = parts(value)
  if (!p) return '—'
  const weekday = WEEKDAYS[p.weekday] ?? ''
  return `${weekday.charAt(0).toUpperCase()}${weekday.slice(1)}, ${formatDate(value)} · ${p.hour}:${p.minute}`
}

/** Whole days from today until the given date (negative when it has passed). */
export function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null
  const target = new Date(`${value.slice(0, 10)}T00:00:00`)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / 86_400_000)
}

export function initials(firstName: string, lastName: string): string {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase()
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return `${formatDate(value)}, ${formatTime(value)}`
}

// The club works in Tashkent time (UTC+5, no daylight saving).
const TASHKENT_OFFSET_MS = 5 * 60 * 60 * 1000

/** ISO timestamp -> value for <input type="datetime-local"> in Tashkent time. */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(new Date(iso).getTime() + TASHKENT_OFFSET_MS).toISOString().slice(0, 16)
}

/** <input type="datetime-local"> value (Tashkent time) -> ISO timestamp with offset. */
export function fromLocalInput(value: string): string | null {
  return value ? `${value}:00+05:00` : null
}

export const USER_STATUS_LABELS: Record<string, string> = {
  PENDING: 'Kutilmoqda',
  ACTIVE: 'Faol',
  BLOCKED: 'Bloklangan',
  INACTIVE: 'Nofaol',
  LEFT: 'Chiqib ketgan',
}

export const BOOK_STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Qoralama',
  ACTIVE: "Faol (o'qilmoqda)",
  COMPLETED: 'Yakunlangan',
  ARCHIVED: 'Arxivlangan',
}

export const QUOTE_STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Qoralama',
  SCHEDULED: 'Rejalashtirilgan',
  SENT: 'Yuborilgan',
  ARCHIVED: 'Arxivlangan',
}

export const EVENT_STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Qoralama',
  PUBLISHED: "E'lon qilingan",
  COMPLETED: "O'tkazildi",
  CANCELLED: 'Bekor qilingan',
}
