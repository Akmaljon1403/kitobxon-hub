import { BookCover } from '../components/BookCover'
import { Avatar } from '../components/Avatar'
import { BenefitCard } from '../components/BenefitCard'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { Book, ClubEvent, ClubTest, MyRanking } from '../types/api'
import { EventCard } from './EventsPage'
import { daysUntil, formatDate, formatEventDate } from '../utils/format'
import { navigate } from '../utils/router'

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

  return (
    <>
      <Card className="flex items-center gap-3">
        <Avatar me={me} size="size-12" />
        <div className="min-w-0">
          <p className="text-sm text-app-hint">Assalomu alaykum,</p>
          <h1 className="truncate text-lg font-semibold">{me.first_name}! 📖</h1>
        </div>
        {ranking.state.status === 'success' && (
          <button
            type="button"
            onClick={() => navigate('/results')}
            className="ml-auto flex flex-col items-end rounded-xl bg-app-surface px-3 py-1.5 active:opacity-70"
          >
            <p className="text-xl font-semibold leading-none tabular-nums">{ranking.state.data.all?.total ?? 0}</p>
            <p className="mt-0.5 text-xs text-app-hint">
              {ranking.state.data.all ? `ball · ${ranking.state.data.all.rank}-o'rin` : 'ball'}
            </p>
          </button>
        )}
      </Card>

      {liveAttendance && (
        <button type="button" className="text-left" onClick={() => navigate('/checkin?scan=1')}>
          <Card className="flex items-center gap-3 border-2 border-app-button">
            <span aria-hidden className="text-3xl">
              ✅
            </span>
            <div className="min-w-0">
              <p className="font-semibold">Davomat ochiq!</p>
              <p className="truncate text-sm text-app-hint">«{liveAttendance.title}» — bosing va QR kodni skanerlang</p>
            </div>
            <span aria-hidden className="ml-auto text-app-link">
              →
            </span>
          </Card>
        </button>
      )}

      <SectionTitle>Joriy kitob</SectionTitle>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && !current && (
        <Card>
          <p className="text-sm text-app-hint">Hozircha faol kitob yo'q. Yangi kitob qo'shilganda shu yerda ko'rinadi.</p>
        </Card>
      )}
      {current && (
        <button type="button" className="text-left" onClick={() => navigate(`/books/${current.id}`)}>
          <Card className="flex gap-3">
            <BookCover url={current.cover_url} title={current.title} className="h-24 w-16 shrink-0" />
            <div className="flex min-w-0 flex-col gap-1">
              <h2 className="line-clamp-2 font-semibold">{current.title}</h2>
              <p className="truncate text-sm text-app-hint">{current.author}</p>
              {current.deadline && (
                <p className="text-xs text-app-hint">
                  Muddat: {formatDate(current.deadline)} · {deadlineText(current.deadline)}
                </p>
              )}
              <p className="mt-auto text-sm font-medium text-app-link">
                {current.my_reading?.status === 'COMPLETED'
                  ? "✅ O'qib tugatdingiz"
                  : current.my_reading
                    ? '📖 O\'qiyapsiz — davom eting'
                    : "Batafsil →"}
              </p>
            </div>
          </Card>
        </button>
      )}

      {nextEvent && (
        <>
          <SectionTitle>Yaqin tadbir</SectionTitle>
          <EventCard event={nextEvent} />
        </>
      )}

      {openTest && (
        <>
          <SectionTitle>Ochiq test</SectionTitle>
          <button type="button" className="text-left" onClick={() => navigate(`/tests/${openTest.id}`)}>
            <Card className="flex items-center gap-3 border-2 border-app-button/40">
              <span aria-hidden className="text-3xl">
                📝
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{openTest.title}</p>
                <p className="text-sm text-app-hint">
                  {openTest.in_progress ? '⏳ Davom ettiring' : `${openTest.max_score} ballgacha`} · yopiladi{' '}
                  {formatEventDate(openTest.ends_at)}
                </p>
              </div>
              <span className="text-app-link">→</span>
            </Card>
          </button>
        </>
      )}

      <BenefitCard />

      <SectionTitle>Bo'limlar</SectionTitle>
      <div className="grid grid-cols-3 gap-2">
        {SHORTCUTS.filter((item) => !item.feature || me?.features?.[item.feature] !== 'off').map((item) => {
          const locked = item.feature !== 'premium' && item.feature && me?.features?.[item.feature] === 'premium'
          const trial = Boolean(item.feature && me?.premium_trial && me.premium_features?.includes(item.feature))
          return (
            <button
              key={item.route}
              type="button"
              onClick={() => navigate(`/${item.route}`)}
              className="relative flex min-h-[86px] flex-col items-center justify-center gap-1 rounded-2xl bg-app-bg px-2 py-3 text-center text-xs font-medium leading-tight shadow-sm active:opacity-70"
            >
              {(locked || trial) && (
                <span aria-label="Premium" title={trial ? 'Premium — sinov davrida ochiq' : 'Premium'} className="absolute right-2 top-1.5 text-xs">
                  💎
                </span>
              )}
              <span aria-hidden className="text-2xl">
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
