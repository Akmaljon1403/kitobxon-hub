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
  graduated?: boolean
  is_admin: boolean
  roles: string[]
  max_course: number
  /** Switched by the super admin: "on", "premium" (needs Premium) or "off". */
  features: Record<string, FeatureAccess>
  is_premium: boolean
  premium_until: string | null
  premium_lifetime?: boolean
  passport_photo: boolean
  /** Premium only thanks to the free trial: Premium features carry a 💎 mark. */
  premium_trial?: boolean
  /** Feature codes that need Premium. */
  premium_features?: string[]
  /** Required channels not joined yet (empty: all good). */
  subscription_missing?: SubscriptionChannel[]
}

export interface SubscriptionChannel {
  title: string
  url: string
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
  /** Finished after the deadline: in the portfolio, without points. */
  late?: boolean
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
  my_shift_id: string | null
  shifts: EventShift[]
}

export interface EventShift {
  id: string
  position: number
  starts_at: string
  ends_at: string
  capacity: number | null
  registered_count: number
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
  premium?: boolean
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
  has_image?: boolean
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
  attended?: boolean | null
  participants: number
  questions: {
    id: string
    type: QuestionType
    text: string
    points: number
    explanation: string | null
    is_correct: boolean
    points_awarded: number
    has_image?: boolean
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
  verify_url?: string | null
  design?: string | null
  rights?: CertificateRights
}

export interface CertificateRights {
  can_download: boolean
  downloads_left: number | null
  premium: boolean
  can_change_design: boolean
  design_changes_left: number
}

export interface CertificateDesign {
  code: string
  title: string
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
  price_uzs: number | null
  stars_now?: number | null
  price_uzs_now?: number | null
}

export interface PremiumStatus {
  is_premium: boolean
  lifetime?: boolean
  until: string | null
  store_open: boolean
  donations_open: boolean
  plans: PremiumPlan[]
  donation_amounts: number[]
  premium_features: { code: string; title: string; description: string }[]
  perks: { icon: string; title: string; description: string }[]
  card: { number: string; holder: string } | null
  trial_days?: number
  discount?: { percent: number; valid_until: string; note: string | null } | null
  stars_packages?: { stars: number; price_uzs: number }[]
}

export interface CardPayment {
  id: string
  kind: 'PREMIUM' | 'DONATION' | 'STARS'
  status: 'PENDING' | 'APPROVED' | 'REJECTED'
  amount_uzs: number
  plan_title: string | null
  created_at: string
  decided_at: string | null
  reject_reason: string | null
  stars?: number | null
  delivered_at?: string | null
}

export interface EventFeedback {
  rating: number
  comment: string | null
  updated_at: string
}

export interface PassportTheme {
  code: string
  title: string
  premium: boolean
  colors: string[]
  selected: boolean
}

export interface PersonalStats {
  months: { month: string; label: string; points: number }[]
  total: number
  breakdown: Record<string, number>
  rank: number | null
  month_rank: number | null
  last_month_rank: number | null
  events_held: number
  events_attended: number
  attendance_rate: number | null
  tests_taken: number
  tests_average_percent: number | null
  test_places: Record<string, number>
  books_completed: number
  streak_weeks: number
  member_days: number
}

export interface PublicGiveaway {
  id: string
  title: string
  reward: string
  rule: 'RANDOM' | 'TEST_TOP' | 'EVENT_PLACES' | 'RANKING_TOP' | 'NEW_MEMBERS'
  rule_title: string
  winners_count: number
  period: string
  premium_bonus: boolean
  audience: 'ALL' | 'ATTENDED' | 'PREMIUM'
  scheduled_at: string | null
  drawn_at: string | null
  winners: { name: string; reason: string; place: number | null }[]
}

export interface MemberGiveaways {
  upcoming: PublicGiveaway[]
  recent: PublicGiveaway[]
}

export interface Referrals {
  enabled: boolean
  link: string | null
  invited: number
  rewarded: number
  points: number
  premium_days: number
  monthly_limit: number
}

export interface ReferralImpact {
  invited: number
  came_to_events: number
  active: number
  friends_points: number
  friends_books: number
  friends_visits: number
  friends_tests: number
  earned_points: number
  earned_premium_days: number
}

export interface InvitedFriend {
  name: string
  joined_at: string | null
  came_to_event: boolean
  active: boolean
  points: number | null
  books: number | null
  visits: number | null
}

export interface InviterRow {
  place: number
  name: string
  friends: number
  me: boolean
}

export interface ReferralBrief extends Referrals {
  impact: ReferralImpact
}

export interface ReferralOverview extends Referrals {
  impact: ReferralImpact
  friend_details: 'FULL' | 'NAMES' | 'COUNT'
  friends: InvitedFriend[]
  leaderboard: { rule: string; items: InviterRow[]; my_place: number | null; my_friends: number } | null
}

export interface ContestRow {
  place: number
  name: string
  friends: number | null
  winner: boolean
  me: boolean
}

export interface MemberContest {
  id: string
  title: string
  description: string | null
  starts_at: string
  ends_at: string
  state: 'upcoming' | 'running' | 'finished'
  rule: string
  min_friends: number
  winners_count: number
  prizes: { place: number; text: string }[]
  participation_points: number
  eligible: boolean
  leaderboard: ContestRow[]
  leaderboard_hidden: boolean
  show_counts: boolean
  my_friends: number
  my_place: number | null
  participants: number
}

export interface TestStandings {
  test_id: string
  title: string
  max_score: number
  event_test: boolean
  participants: number
  rows: { place: number; prize_place: number | null; name: string; score: number; attended: boolean | null; me: boolean }[]
}
