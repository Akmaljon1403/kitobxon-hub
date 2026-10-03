import { BookCover } from '../components/BookCover'
import { Avatar } from '../components/Avatar'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { Book, ClubEvent, ClubTest, MyRanking, Page } from '../types/api'
import { EventCard } from './EventsPage'
import { daysUntil, formatDate, formatEventDate } from '../utils/format'
import { navigate } from '../utils/router'

const SHORTCUTS: { route: string; icon: string; label: string; feature?: string }[] = [
  { route: 'books', icon: '📚', label: 'Kitoblar' },
  { route: 'events', icon: '📅', label: 'Tadbirlar' },
  { route: 'checkin', icon: '✅', label: 'Davomat' },
  { route: 'tests', icon: '📝', label: 'Testlar' },
  { route: 'results', icon: '📊', label: 'Natijalarim' },
  { route: 'ranking', icon: '🏆', label: 'Reyting', feature: 'ranking' },
  { route: 'achievements', icon: '🏅', label: 'Yutuqlar', feature: 'achievements' },
  { route: 'profile', icon: '🪪', label: 'Pasportim' },
  { route: 'rewards', icon: '🎁', label: "Sovg'alar", feature: 'rewards' },
  { route: 'certificates', icon: '🎓', label: 'Sertifikatlar', feature: 'certificates' },
  { route: 'premium', icon: '💎', label: 'Premium', feature: 'premium' },
]

function deadlineText(deadline: string | null): string | null {
  const days = daysUntil(deadline)
  if (days === null) return null
  if (days < 0) return 'Muddat tugagan'
  if (days === 0) return 'Bugun oxirgi kun'
  return `${days} kun qoldi`
}

export function HomePage() {
  const { me, api } = useAuth()
  const { state, reload } = useAsync((signal) => api<Page<Book>>('/api/v1/books?limit=3', { signal }))
  const events = useAsync((signal) => api<Page<ClubEvent>>('/api/v1/events?scope=upcoming&limit=1', { signal }))
  const ranking = useAsync((signal) => api<MyRanking>('/api/v1/me/ranking', { signal }))
  const tests = useAsync((signal) => api<ClubTest[]>('/api/v1/tests', { signal }))
  const attendance = useAsync((signal) =>
    api<{ event_id: string; title: string; checked_in: boolean }[]>('/api/v1/attendance/open', { signal }),
  )
  const liveAttendance =
    attendance.state.status === 'success' ? attendance.state.data.find((item) => !item.checked_in) : undefined
  const openTest =
    tests.state.status === 'success'
      ? tests.state.data.find((test) => test.state === 'OPEN' && (test.in_progress || test.attempts.length === 0))
      : undefined
  if (!me) return null

  const current = state.status === 'success' ? state.data.items.find((book) => book.status === 'ACTIVE') : undefined

  return (
    <>
      <Card className="flex items-center gap-3">
        <Avatar me={me} size="size-12" />
        <div className="min-w-0">
          <p className="text-sm text-app-hint">Assalomu alaykum,</p>
          <h1 className="truncate text-lg font-semibold">{me.first_name}! 📖</h1>
        </div>
        {ranking.state.status === 'success' && (
          <button type="button" onClick={() => navigate('/results')} className="ml-auto text-right">
            <p className="text-xl font-semibold tabular-nums">{ranking.state.data.all?.total ?? 0}</p>
            <p className="text-xs text-app-hint">
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

      {events.state.status === 'success' && events.state.data.items[0] && (
        <>
          <SectionTitle>Yaqin tadbir</SectionTitle>
          <EventCard event={events.state.data.items[0]} />
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

      <SectionTitle>Bo'limlar</SectionTitle>
      <div className="grid grid-cols-3 gap-2">
        {SHORTCUTS.filter((item) => !item.feature || me?.features?.[item.feature] !== 'off').map((item) => {
          const locked = item.feature !== 'premium' && item.feature && me?.features?.[item.feature] === 'premium'
          return (
            <button
              key={item.route}
              type="button"
              onClick={() => navigate(`/${item.route}`)}
              className="relative flex flex-col items-center gap-1 rounded-2xl bg-app-bg px-2 py-4 text-sm shadow-sm active:opacity-70"
            >
              {locked && (
                <span aria-label="Premium" className="absolute right-2 top-1.5 text-xs">
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
