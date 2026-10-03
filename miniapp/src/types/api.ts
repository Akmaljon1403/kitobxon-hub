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
  /** Membership number printed on the Kitobxon passport, e.g. KH-000042. */
  member_number: string
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
  /** Switched by the super admin: "on", "premium" (needs Premium) or "off". */
  features: Record<string, FeatureAccess>
  is_premium: boolean
  premium_until: string | null
}

export type FeatureAccess = 'on' | 'premium' | 'off'


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

export type EventStatus = 'DRAFT' | 'PUBLISHED' | 'COMPLETED' | 'CANCELLED'
export type AttendanceStatus = 'VERIFIED' | 'SUSPICIOUS' | 'REVOKED'

export interface ClubEvent {
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
  capacity: number | null
  status: EventStatus
  registered_count: number
  attended_count: number
  is_registered: boolean
  my_attendance: AttendanceStatus | null
}

export interface CheckInResult {
  event_id: string
  event_title: string
  points: number
  checked_in_at: string
}

export interface ScoreEntry {
  id: string
  amount: number
  category: string
  effective_category: string
  source_type: string | null
  source_title: string | null
  reason: string | null
  is_reversed: boolean
  created_at: string
}

export interface MyScores {
  total: number
  breakdown: Record<string, number>
  season: { name: string | null; total: number } | null
  history: ScoreEntry[]
}

export interface RankingRow {
  rank: number
  name: string
  faculty: string | null
  group_name: string | null
  total: number
  attendance: number
  tests: number
  is_me: boolean
}

export interface Ranking {
  period: 'week' | 'month' | 'season' | 'all'
  scope: 'all' | 'faculty' | 'group'
  starts_at: string | null
  items: RankingRow[]
  me: RankingRow | null
}

export interface FacultyRanking {
  rank: number
  faculty: string
  members: number
  total: number
  average: number
}

export interface MyRanking {
  week: RankingRow | null
  month: RankingRow | null
  all: RankingRow | null
}

export type TestState = 'DRAFT' | 'UPCOMING' | 'OPEN' | 'CLOSED'
export type AttemptStatus = 'IN_PROGRESS' | 'SUBMITTED' | 'EXPIRED'
export type QuestionType = 'SINGLE_CHOICE' | 'MULTIPLE_CHOICE'

export interface MyAttempt {
  attempt_number: number
  status: AttemptStatus
  score: number | null
  correct_count: number | null
  question_count: number
  submitted_at: string | null
}

export interface ClubTest {
  id: string
  title: string
  description: string | null
  book_id: string | null
  book_title: string | null
  starts_at: string
  ends_at: string
  duration_minutes: number
  max_score: number
  passing_score: number
  attempts_allowed: number
  question_count: number
  state: TestState
  attempts: MyAttempt[]
  best_score: number | null
  in_progress: boolean
  can_start: boolean
  review_available: boolean
}

export interface AttemptQuestion {
  id: string
  type: QuestionType
  text: string
  points: number
  options: { id: string; text: string }[]
}

export interface RunningAttempt {
  attempt_id: string
  test_id: string
  title: string
  attempt_number: number
  started_at: string
  deadline_at: string
  server_now: string
  questions: AttemptQuestion[]
  answers: Record<string, string[]>
}

export interface AttemptResult {
  attempt_id: string
  status: AttemptStatus
  score: number
  max_score: number
  passing_score: number
  passed: boolean
  correct_count: number
  question_count: number
  points_awarded: number
  submitted_at: string | null
  attempts_left: number
  review_available_at: string
}

export interface TestReview {
  test_id: string
  title: string
  score: number
  max_score: number
  correct_count: number
  question_count: number
  place: number | null
  participants: number
  questions: {
    id: string
    type: QuestionType
    text: string
    points: number
    explanation: string | null
    is_correct: boolean
    points_awarded: number
    options: { id: string; text: string; is_correct: boolean; selected: boolean }[]
  }[]
}

export interface MemberAchievement {
  code: string
  title: string
  description: string
  icon: string
  criteria: string
  threshold: number
  points: number
  progress: number | null
  unlocked_at: string | null
}

export interface MemberReward {
  id: string
  title: string
  description: string | null
  type: 'BOOK' | 'CERTIFICATE' | 'SUBSCRIPTION_CODE' | 'PARTNER_DISCOUNT' | 'OTHER'
  value: string | null
  expires_at: string | null
  status: 'ASSIGNED' | 'DELIVERED' | 'REDEEMED' | 'REVOKED'
  has_code: boolean
  assigned_at: string
  redeemed_at: string | null
}

export type CertificateKind = 'TEST_PLACE' | 'MONTHLY_TOP' | 'MANUAL'

export interface Certificate {
  id: string
  kind: CertificateKind
  place: number | null
  title: string
  description: string
  issued_at: string
  code: string
}

export interface DownloadLink {
  url: string
  filename: string
  expires_in: number
}

export interface PremiumPlan {
  id: string
  title: string
  description: string | null
  stars: number
  days: number
}

export interface PremiumStatus {
  is_premium: boolean
  until: string | null
  store_open: boolean
  donations_open: boolean
  plans: PremiumPlan[]
  donation_amounts: number[]
  premium_features: { code: string; title: string; description: string }[]
}

export interface EventFeedback {
  rating: number
  comment: string | null
  updated_at: string
}
