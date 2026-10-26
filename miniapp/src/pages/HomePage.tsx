import { Avatar } from '../components/Avatar'
import { BenefitCard } from '../components/BenefitCard'
import { BookCover } from '../components/BookCover'
import { CardListSkeleton, ErrorState } from '../components/StateViews'
import { Badge, Card, IconBadge, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { Book, ClubEvent, ClubTest, MyRanking } from '../types/api'
import { daysUntil, formatDate, formatEventDate } from '../utils/format'
import { navigate } from '../utils/router'
import { selectionHaptic } from '../utils/telegram'
import { EventCard } from './EventsPage'

const SHORTCUTS: { route: string; icon: string; label: string; feature?: string }[] = [
  { route: 'books', icon: '📚', label: 'Kitoblar' },
  { route: 'shelf', icon: '📖', label: 'Javonim', feature: 'shelf' },
  { route: 'missions', icon: '🎯', label: 'Missiyalar', feature: 'missions' },
  { route: 'quotes', icon: '💬', label: 'Iqtiboslarim', feature: 'quote_box' },
  { route: 'community', icon: '🌍', label: "A'zolar fikrlari", feature: 'community' },
  { route: 'events', icon: '📅', label: 'Tadbirlar' },
  { route: 'checkin', icon: '✅', label: 'Davomat' },
  { route: 'tests', icon: '📝', label: 'Testlar' },
  { route: 'results', icon: '📊', label: 'Natijalarim' },
  { route: 'stats', icon: '📈', label: 'Statistikam', feature: 'personal_stats' },
  { route: 'ranking', icon: '🏆', label: 'Reyting', feature: 'ranking' },
  { route: 'league', icon: '🏛', label: 'Fakultetlar ligasi', feature: 'faculty_league' },
  { route: 'achievements', icon: '🏅', label: 'Yutuqlar', feature: 'achievements' },
  { route: 'profile', icon: '🪪', label: 'Pasportim' },
  { route: 'rewards', icon: '🎁', label: "Sovg'alar", feature: 'rewards' },
  { route: 'certificates', icon: '🎓', label: 'Sertifikatlar', feature: 'certificates' },
  { route: 'card', icon: '🪪', label: 'Kartam', feature: 'reading_card' },
  { route: 'invite', icon: '🎁', label: 'Sizning foydangiz' },
  { route: 'premium', icon: '💎', label: 'Premium', feature: 'premium' },
  { route: 'help', icon: '❓', label: 'Yordam' },
]

function deadlineText(deadline: string | null): string | null {
  const days = daysUntil(deadline)
  if (days === null) return null
  if (days < 0) return 'Muddat tugagan'
  if (days === 0) return 'Bugun oxirgi kun'
  return `${days} kun qoldi`
}

interface HomeData {
  book: Book | null
  event: ClubEvent | null
  test: ClubTest | null
  attendance: { event_id: string; title: string; checked_in: boolean } | null
}

function go(path: string): void {
  selectionHaptic()
  navigate(path)
}

/** The reader's current club book — the everyday primary action on the home screen. */
function ContinueReading({ book }: { book: Book }) {
  const status = book.my_reading?.status
  const cta = status === 'COMPLETED' ? 'Ko‘rish →' : status === 'READING' ? 'Davom eting →' : 'Boshlash →'
  return (
    <button type="button" className="w-full text-left" onClick={() => go(`/books/${book.id}`)}>
      <Card interactive className="flex gap-3.5">
        <BookCover url={book.cover_url} title={book.title} className="h-28 w-[4.5rem] shrink-0 rounded-lg shadow-[var(--shadow-card)]" />
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-wrap gap-1.5">
            {status === 'READING' && <Badge tone="brand">📖 O‘qiyapsiz</Badge>}
            {status === 'COMPLETED' && <Badge tone="success">✅ Tugatdingiz</Badge>}
            {book.deadline && !status && <Badge tone="warning">{deadlineText(book.deadline)}</Badge>}
          </div>
          <h2 className="mt-1 line-clamp-2 font-serif text-[17px] font-semibold leading-snug">{book.title}</h2>
          <p className="truncate text-sm text-app-hint">{book.author}</p>
          {book.deadline && status !== 'COMPLETED' && (
            <p className="mt-0.5 text-xs text-app-hint">Muddat: {formatDate(book.deadline)}</p>
          )}
          <span className="mt-auto pt-1.5 text-sm font-semibold text-brand-600 dark:text-brand-300">{cta}</span>
        </div>
      </Card>
    </button>
  )
}

export function HomePage() {
  const { me, api } = useAuth()
  // One request for the whole home (active book, next event, open test, live check-in). The points badge
  // stays its own call because it is feature-gated.
  const { state, reload } = useAsync((signal) => api<HomeData>('/api/v1/me/home', { signal }))
  const ranking = useAsync((signal) => api<MyRanking>('/api/v1/me/ranking', { signal }))
  if (!me) return null

  const home = state.status === 'success' ? state.data : null
  const current = home?.book ?? undefined
  const nextEvent = home?.event ?? undefined
  const openTest = home?.test ?? undefined
  const liveAttendance = home?.attendance && !home.attendance.checked_in ? home.attendance : undefined
  const points = ranking.state.status === 'success' ? ranking.state.data.all : null
  const shortcuts = SHORTCUTS.filter((item) => !item.feature || me.features?.[item.feature] !== 'off')

  return (
    <>
      {/* Hero: greeting + points. White-on-brand for a distinctive, premium first impression. */}
      <section className="overflow-hidden rounded-3xl bg-brand-gradient p-4 text-white shadow-[var(--shadow-brand)]">
        <div className="flex items-center gap-3">
          <span className="rounded-full ring-2 ring-white/40">
            <Avatar me={me} size="size-12" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm text-white/80">Assalomu alaykum,</p>
            <h1 className="truncate font-serif text-xl font-bold">{me.first_name}! 📖</h1>
          </div>
          {points && (
            <button
              type="button"
              onClick={() => go('/results')}
              className="flex flex-col items-center rounded-2xl bg-white/15 px-3.5 py-2 backdrop-blur active:scale-95"
            >
              <span className="text-xl font-bold leading-none tabular-nums">{points.total}</span>
              <span className="mt-0.5 text-[11px] text-white/80">ball · {points.rank}-o‘rin</span>
            </button>
          )}
        </div>
      </section>

      {/* Time-sensitive: an open check-in comes first. */}
      {liveAttendance && (
        <button type="button" className="w-full text-left" onClick={() => go('/checkin?scan=1')}>
          <Card interactive tone="brand" className="flex items-center gap-3">
            <IconBadge tone="brand">✅</IconBadge>
            <div className="min-w-0 flex-1">
              <p className="font-semibold">Davomat ochiq!</p>
              <p className="truncate text-sm text-app-hint">«{liveAttendance.title}» — bosing va QR kodni skanerlang</p>
            </div>
            <span aria-hidden className="text-brand-600 dark:text-brand-300">→</span>
          </Card>
        </button>
      )}

      <SectionTitle>Joriy kitob</SectionTitle>
      {state.status === 'loading' && <CardListSkeleton rows={1} />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && !current && (
        <Card>
          <p className="text-sm text-app-hint">Hozircha faol kitob yo‘q. Yangi kitob qo‘shilganda shu yerda ko‘rinadi.</p>
        </Card>
      )}
      {current && <ContinueReading book={current} />}

      {openTest && (
        <>
          <SectionTitle>Ochiq test</SectionTitle>
          <button type="button" className="w-full text-left" onClick={() => go(`/tests/${openTest.id}`)}>
            <Card interactive className="flex items-center gap-3">
              <IconBadge tone="gold">📝</IconBadge>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{openTest.title}</p>
                <p className="truncate text-sm text-app-hint">
                  {openTest.in_progress ? '⏳ Davom ettiring' : `${openTest.max_score} ballgacha`} · yopiladi{' '}
                  {formatEventDate(openTest.ends_at)}
                </p>
              </div>
              <span aria-hidden className="text-brand-600 dark:text-brand-300">→</span>
            </Card>
          </button>
        </>
      )}

      {nextEvent && (
        <>
          <SectionTitle>Yaqin tadbir</SectionTitle>
          <EventCard event={nextEvent} />
        </>
      )}

      <BenefitCard />

      <SectionTitle>Bo‘limlar</SectionTitle>
      <div className="grid grid-cols-3 gap-2.5">
        {shortcuts.map((item) => {
          const locked = item.feature !== 'premium' && item.feature && me.features?.[item.feature] === 'premium'
          const trial = Boolean(item.feature && me.premium_trial && me.premium_features?.includes(item.feature))
          return (
            <button
              key={item.route}
              type="button"
              onClick={() => go(`/${item.route}`)}
              className="relative flex min-h-[92px] flex-col items-center justify-center gap-2 rounded-2xl border border-[color:var(--hairline)] bg-app-bg px-2 py-3 text-center text-xs font-medium leading-tight shadow-[var(--shadow-card)] transition-transform active:scale-95"
            >
              {(locked || trial) && (
                <span
                  aria-label="Premium"
                  title={trial ? 'Premium — sinov davrida ochiq' : 'Premium'}
                  className="absolute right-1.5 top-1.5 text-[11px]"
                >
                  💎
                </span>
              )}
              <span aria-hidden className="grid size-10 place-items-center rounded-xl bg-brand-500/12 text-2xl">
                {item.icon}
              </span>
              {item.label}
            </button>
          )
        })}
      </div>
    </>
  )
}
