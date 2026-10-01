const MONTHS = [
  'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
  'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
]

/** "15-oktabr" (current year) or "15-oktabr, 2027". Accepts "2026-10-15" or ISO timestamps. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const base = `${date.getDate()}-${MONTHS[date.getMonth()]}`
  return date.getFullYear() === new Date().getFullYear() ? base : `${base}, ${date.getFullYear()}`
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
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  const time = date.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${formatDate(value)}, ${time}`
}

export const USER_STATUS_LABELS: Record<string, string> = {
  PENDING: 'Kutilmoqda',
  ACTIVE: 'Faol',
  BLOCKED: 'Bloklangan',
  INACTIVE: 'Nofaol',
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
