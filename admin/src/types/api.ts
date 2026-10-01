// Response types of the Kitobxon Hub admin API (see /api/docs on the server).

export type UserStatus = 'PENDING' | 'ACTIVE' | 'BLOCKED' | 'INACTIVE'
export type BookStatus = 'DRAFT' | 'ACTIVE' | 'COMPLETED' | 'ARCHIVED'
export type QuoteStatus = 'DRAFT' | 'SCHEDULED' | 'SENT' | 'ARCHIVED'

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface TokenResponse {
  access_token: string
  expires_at: string
  scope: 'member' | 'admin'
}

export interface AdminSelf {
  id: string
  first_name: string
  last_name: string
  roles: string[]
  permissions: string[]
  is_super_admin: boolean
}

export interface Faculty {
  id: string
  name: string
  short_name: string | null
  is_active: boolean
  sort_order: number
}

export interface AdminUser {
  id: string
  first_name: string
  last_name: string
  telegram_username: string | null
  phone: string | null
  faculty_id: string | null
  faculty_name: string | null
  course: number | null
  group_name: string | null
  status: UserStatus
  registered_at: string | null
  last_seen_at: string | null
  roles?: string[]
}

export interface Book {
  id: string
  title: string
  author: string
  description: string | null
  cover_url: string | null
  source_url: string | null
  language: string
  pages: number | null
  start_date: string | null
  deadline: string | null
  status: BookStatus
  readers_count: number
  completed_count: number
  created_at: string
  updated_at: string
}

export interface Reader {
  user_id: string
  first_name: string
  last_name: string
  faculty_name: string | null
  course: number | null
  group_name: string | null
  status: 'READING' | 'COMPLETED'
  started_at: string
  completed_at: string | null
  verified_at: string | null
}

export interface Quote {
  id: string
  book_id: string | null
  book_title: string | null
  text: string
  author: string | null
  source: string | null
  scheduled_date: string | null
  status: QuoteStatus
  sent_at: string | null
  created_at: string
}

export interface Setting {
  key: string
  group: string
  kind: 'int' | 'bool' | 'int_list' | 'time' | 'choice' | 'text'
  value: unknown
  default: unknown
  description: string
  choices: string[]
}

export interface Permission {
  code: string
  group: string
  description: string
}

export interface AdminAccount {
  user_id: string
  first_name: string
  last_name: string
  telegram_username: string | null
  roles: string[]
  direct_permissions: string[]
  effective_permissions: string[]
}

export interface AuditEntry {
  id: string
  actor_user_id: string | null
  actor_name: string | null
  action: string
  entity_type: string
  entity_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  reason: string | null
  request_id: string | null
  created_at: string
}

export interface Statistics {
  users: { total: number; active: number; pending: number; blocked: number; inactive: number; new_last_7_days: number }
  books: { total: number; active: number; draft: number; readers: number; completions: number }
  faculties: { name: string; members: number }[]
}

export type EventStatus = 'DRAFT' | 'PUBLISHED' | 'COMPLETED' | 'CANCELLED'
export type AttendanceStatus = 'VERIFIED' | 'SUSPICIOUS' | 'REVOKED'

export interface AdminEvent {
  id: string
  title: string
  description: string | null
  book_id: string | null
  book_title: string | null
  location: string | null
  starts_at: string
  ends_at: string
  attendance_opens_at: string
  attendance_closes_at: string
  attendance_points: number
  attendance_points_override: number | null
  capacity: number | null
  status: EventStatus
  registered_count: number
  attended_count: number
  attendance_open: boolean
  created_at: string
}

export interface AttendanceRecord {
  id: string
  user_id: string
  first_name: string
  last_name: string
  faculty_name: string | null
  course: number | null
  group_name: string | null
  method: 'QR' | 'CODE' | 'MANUAL'
  status: AttendanceStatus
  checked_in_at: string
  suspicious_reason: string | null
  note: string | null
}

export interface AttendanceOverview {
  event_id: string
  is_open: boolean
  closes_at: string | null
  registered_count: number
  attended_count: number
  records: AttendanceRecord[]
}

export interface AttendanceToken {
  qr_payload: string
  token: string
  code: string
  expires_at: string
  rotates_at: string
  session_closes_at: string
}
