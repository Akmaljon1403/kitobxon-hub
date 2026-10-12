// Response types of the Kitobxon Hub admin API (see /api/docs on the server).

export type UserStatus = 'PENDING' | 'ACTIVE' | 'BLOCKED' | 'INACTIVE' | 'LEFT'
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
  left_at?: string | null
  left_reason?: string | null
  restore_requested_at?: string | null
  graduated_at?: string | null
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
  /** The cover shown to members: the uploaded picture or the cover link. */
  cover_image?: string | null
  cover_uploaded?: boolean
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
export type AttendanceStatus = 'VERIFIED' | 'SUSPICIOUS' | 'REVOKED' | 'PENDING'

export interface EventShift {
  id: string
  position: number
  starts_at: string
  ends_at: string
  attendance_opens_at: string
  attendance_closes_at: string
  capacity: number | null
  registered_count: number
}

export interface TopEvent {
  event_id: string
  title: string
  starts_at: string
  average: number
  ratings: number
}

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
  shifts: EventShift[]
  rating: number | null
  ratings_count: number
  pending_requests: number
  certificate_background: boolean
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
  requested_by_name: string | null
}

export interface AttendanceOverview {
  event_id: string
  is_open: boolean
  closes_at: string | null
  shift: number | null
  can_approve: boolean
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

export interface ScoreEntry {
  id: string
  user_id: string
  user_name: string
  amount: number
  category: string
  effective_category: string
  source_type: string | null
  source_title: string | null
  reason: string | null
  is_reversed: boolean
  created_at: string
}

export interface ScoreSummary {
  total: number
  breakdown: Record<string, number>
  season: { name: string | null; total: number } | null
}

export interface Season {
  id: string
  name: string
  starts_on: string
  ends_on: string
  status: string
  is_current: boolean
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

export type TestStatus = 'DRAFT' | 'PUBLISHED' | 'CLOSED' | 'ARCHIVED'
export type TestState = 'DRAFT' | 'UPCOMING' | 'OPEN' | 'CLOSED'
export type QuestionType = 'SINGLE_CHOICE' | 'MULTIPLE_CHOICE'
export type AttemptStatus = 'IN_PROGRESS' | 'SUBMITTED' | 'EXPIRED'

export interface AdminTest {
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
  shuffle_questions: boolean
  shuffle_options: boolean
  status: TestStatus
  state: TestState
  question_count: number
  questions_per_attempt: number | null
  participant_count: number
  published_at: string | null
  rank_bonus_awarded: boolean
  created_at: string
  event_id: string | null
  certificate_background: boolean
}

export interface AdminQuestion {
  id?: string
  type: QuestionType
  text: string
  points: number
  explanation: string | null
  options: { id?: string; text: string; is_correct: boolean }[]
  /** A picture for the question (stored file). */
  image_key?: string | null
}

export interface QuestionImport {
  questions: AdminQuestion[]
  warnings: string[]
}

export interface AdminTestDetail extends AdminTest {
  questions: AdminQuestion[]
}

export interface TestResultRow {
  attempt_id: string
  user_id: string
  first_name: string
  last_name: string
  faculty: string | null
  course: number | null
  group_name: string | null
  attempt_number: number
  status: AttemptStatus
  score: number | null
  correct_count: number | null
  question_count: number
  passed: boolean | null
  started_at: string
  submitted_at: string | null
  duration_seconds: number | null
  signals: number
  place: number | null
  /** A test of an event: was the member at the event? (null: the test has no event) */
  attended?: boolean | null
  /** The place counted for prizes (attendees only). */
  prize_place?: number | null
}

export interface TestResults {
  test: AdminTest
  participants: number
  passed: number
  average_score: number | null
  items: TestResultRow[]
}

export interface AttemptDetail {
  attempt_id: string
  member: string
  status: AttemptStatus
  score: number | null
  started_at: string
  deadline_at: string
  submitted_at: string | null
  answers: { question: string; selected: string[]; correct: string[]; is_correct: boolean | null; answered_at: string | null }[]
  activity: { type: string; at: string; details: Record<string, unknown> | null }[]
}

export interface NotificationSummary {
  pending: number
  sent_24h: number
  failed_24h: number
  skipped_24h: number
  worker_enabled: boolean
  bot_configured: boolean
  recent_broadcasts: {
    at: string
    actor: string | null
    message: string
    recipients: number
    filters: Record<string, unknown>
    broadcast_id: string | null
    scheduled_at: string | null
    waiting: number
  }[]
}

export interface AdminAchievement {
  id: string
  code: string
  title: string
  description: string
  icon: string
  criteria: string
  threshold: number
  points: number
  is_active: boolean
  sort_order: number
  holders: number
}

export interface AchievementHolder {
  id: string
  user_id: string
  first_name: string
  last_name: string
  group_name: string | null
  unlocked_at: string
  granted: boolean
}

export type ReportStatus = 'DRAFT' | 'AI_GENERATED' | 'REVIEW' | 'APPROVED' | 'PDF_GENERATED' | 'ARCHIVED'

export type ReportKind = 'EVENT' | 'PERIOD' | 'GENERAL'

export interface ReportListItem {
  id: string
  kind: ReportKind
  event_id: string | null
  /** What the report is about: the event, the period or "Umumiy hisobot". */
  event_title: string
  version: number
  status: ReportStatus
  title: string
  created_at: string
  approved_at: string | null
  pdf_ready: boolean
}

/** Facts loaded from the database; which parts exist depends on the report kind. */
export interface ReportFacts {
  organization: string
  club: string
  event?: {
    title: string
    date: string
    time: string
    location: string | null
    book_title: string | null
    book_author: string | null
    responsible: string | null
  }
  attendance?: {
    registered: number
    attended: number
    attended_registered: number
    walk_ins: number
    rate_percent: number | null
    suspicious: number
  }
  period?: { label: string; start: string; end: string }
  summary?: {
    events: number
    attendances: number
    participants: number
    new_members: number
    active_members: number
    books_completed: number
    certificates: number
  }
  events?: { title: string; date: string; attended: number }[]
  top_members?: { place: number; name: string; faculty: string | null; points: number }[]
  feedback?: { count: number; average: number | null }
  faculties?: { name: string; attended: number }[]
  tests?: { title: string; participants: number; average_score: number; max_score: number; passed?: number }[]
  date?: string
  prepared_at: string
}

export interface ReportDetail {
  id: string
  kind: ReportKind
  event_id: string | null
  period_start: string | null
  period_end: string | null
  version: number
  status: ReportStatus
  title: string
  objective: string | null
  activity_description: string | null
  results: string | null
  conclusion: string | null
  recommendations: string | null
  body_text: string | null
  facts: ReportFacts
  photos: { id: string; caption: string | null; size_bytes: number }[]
  number_issues: string[]
  ai_available: boolean
  ai_model: string | null
  ai_generated_at: string | null
  approved_by: string | null
  approved_at: string | null
  pdf_ready: boolean
  created_at: string
}

export type RewardType = 'BOOK' | 'CERTIFICATE' | 'SUBSCRIPTION_CODE' | 'PARTNER_DISCOUNT' | 'OTHER'

export interface AdminReward {
  id: string
  title: string
  description: string | null
  type: RewardType
  value: string | null
  expires_at: string | null
  status: 'ACTIVE' | 'INACTIVE' | 'ARCHIVED'
  codes_total: number
  codes_available: number
  recipients: number
  created_at: string
}

export interface RewardCodeRow {
  id: string
  masked: string
  status: 'AVAILABLE' | 'ASSIGNED' | 'REDEEMED' | 'EXPIRED' | 'REVOKED'
  expires_at: string | null
  assigned_to: string | null
  created_at: string
}

export interface RewardRecipient {
  id: string
  user_id: string
  first_name: string
  last_name: string
  group_name: string | null
  status: 'ASSIGNED' | 'DELIVERED' | 'REDEEMED' | 'REVOKED'
  has_code: boolean
  note: string | null
  assigned_at: string
  delivered_at: string | null
  redeemed_at: string | null
}

export type GiveawayRule = 'RANDOM' | 'TEST_TOP' | 'EVENT_PLACES' | 'RANKING_TOP' | 'NEW_MEMBERS'
export type GiveawayPrize = 'CODES' | 'PREMIUM_DAYS' | 'PREMIUM_DISCOUNT'
export type GiveawayAudience = 'ALL' | 'ATTENDED' | 'PREMIUM'
export type GiveawayStatus = 'DRAFT' | 'SCHEDULED' | 'DONE' | 'CANCELLED'

export interface GiveawayWinner {
  user_id: string | null
  name: string
  full_name: string | null
  reason: string
  place: number | null
  error?: string | null
}

export interface Giveaway {
  id: string
  title: string
  prize: GiveawayPrize
  prize_value: number | null
  reward_id: string | null
  reward_title: string
  codes_available: number | null
  rule: GiveawayRule
  rule_title: string
  audience: GiveawayAudience
  winners_count: number
  premium_bonus: boolean
  period_start: string
  period_end: string
  period_label: string
  status: GiveawayStatus
  scheduled_at: string | null
  announce: boolean
  repeat_monthly: boolean
  drawn_at: string | null
  seed: string | null
  winners: GiveawayWinner[]
  created_at: string
}

export interface GiveawayPreview {
  eligible: number
  premium: number
  winners: GiveawayWinner[]
  codes_available: number | null
  notes: string[]
}

export type ChannelPostKind = 'EVENT' | 'EVENT_REMINDER' | 'BOOK' | 'READING_NUDGE' | 'QUOTE' | 'RESULTS' | 'INVITE' | 'MANUAL'

export interface ChannelPost {
  id: string
  kind: ChannelPostKind
  text: string
  has_photo: boolean
  has_sticker: boolean
  status: 'PENDING' | 'SENT' | 'FAILED' | 'CANCELLED'
  scheduled_at: string
  sent_at: string | null
  last_error: string | null
  manual: boolean
  plain_text: string
  in_review: boolean
  reviewed_at: string | null
}

export interface ChannelSticker {
  id: string
  emoji: string | null
  set_name: string | null
  is_animated: boolean
  mood: 'CELEBRATE' | 'READING' | 'WELCOME' | 'ANY'
  created_at: string
}

export interface ChannelOverview {
  enabled: boolean
  chat_id: string | null
  link: string | null
  pending: number
  last_sent_at: string | null
  last_error: string | null
  posts: ChannelPost[]
  stickers: ChannelSticker[]
}

export interface TestPlace {
  place: number
  user_id: string
  name: string
  group_name: string | null
  score: number
  max_score: number
  given_reward: string | null
  given_at: string | null
}

export interface TestWinners {
  test_id: string
  title: string
  event_title: string | null
  closed_at: string
  places: TestPlace[]
}
