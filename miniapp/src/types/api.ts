// Response types of the Kitobxon Hub API used by the Mini App (see /api/docs on the server).

export type UserStatus = 'PENDING' | 'ACTIVE' | 'BLOCKED' | 'INACTIVE'
export type BookStatus = 'DRAFT' | 'ACTIVE' | 'COMPLETED' | 'ARCHIVED'
export type ReadingStatus = 'READING' | 'COMPLETED'

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface PublicMeta {
  app_name: string
  version: string
  bot_username: string | null
  timezone: string
}

export interface TokenResponse {
  access_token: string
  expires_at: string
  scope: 'member' | 'admin'
}

export interface Faculty {
  id: string
  name: string
  short_name: string | null
}

export interface Me {
  id: string
  first_name: string
  last_name: string
  telegram_username: string | null
  photo_url: string | null
  phone: string | null
  faculty: Faculty | null
  course: number | null
  group_name: string | null
  status: UserStatus
  registered_at: string | null
  is_admin: boolean
  roles: string[]
  max_course: number
}

export interface NotificationSettings {
  event_reminders: boolean
  test_reminders: boolean
  reading_reminders: boolean
  quote_of_day: boolean
  ranking_updates: boolean
  achievement_alerts: boolean
}

export interface MyReading {
  status: ReadingStatus
  started_at: string
  completed_at: string | null
  verified: boolean
  verification_required: boolean
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
  my_reading: MyReading | null
}

export interface Quote {
  id: string
  text: string
  author: string | null
  source: string | null
}

export interface BookDetail extends Book {
  quotes: Quote[]
}
