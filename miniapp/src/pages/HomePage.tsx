import { Avatar } from '../components/Avatar'
import { BenefitCard } from '../components/BenefitCard'
import { BookCover } from '../components/BookCover'
import { Icon, type IconName } from '../components/Icon'
import { CardListSkeleton, ErrorState } from '../components/StateViews'
import { Badge, Card, FeatureTile, SectionTitle, type TileTone } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { Book, ClubEvent, ClubTest, MyRanking, Shelf } from '../types/api'
import { daysUntil, formatDate, formatEventDate } from '../utils/format'
import { navigate } from '../utils/router'
import { selectionHaptic } from '../utils/telegram'
import { EventCard } from './EventsPage'

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
  const cta = status === 'COMPLETED' ? 'Ko‘rish' : status === 'READING' ? 'Davom eting' : 'Boshlash'
  return (
    <button type="button" className="w-full text-left" onClick={() => go(`/books/${book.id}`)}>
      <Card interactive className="flex gap-3.5">
        <BookCover url={book.cover_url} title={book.title} className="h-28 w-[4.5rem] shrink-0 rounded-lg shadow-[var(--shadow-card)]" />
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-wrap gap-1.5">
            {status === 'READING' && (
              <Badge tone="brand">
                <Icon name="book-open" size={13} /> O‘qiyapsiz
              </Badge>
            )}
            {status === 'COMPLETED' && (
              <Badge tone="success">
                <Icon name="check-circle" size={13} /> Tugatdingiz
              </Badge>
            )}
            {book.deadline && !status && <Badge tone="warning">{deadlineText(book.deadline)}</Badge>}
          </div>
          <h2 className="mt-1 line-clamp-2 font-serif text-[17px] font-semibold leading-snug">{book.title}</h2>
          <p className="truncate text-sm text-app-hint">{book.author}</p>
          {book.deadline && status !== 'COMPLETED' && (
            <p className="mt-0.5 text-xs text-app-hint">Muddat: {formatDate(book.deadline)}</p>
          )}
          <span className="mt-auto flex items-center gap-1 pt-1.5 text-sm font-semibold text-brand-600 dark:text-brand-300">
            {cta} <Icon name="arrow-right" size={15} />
          </span>
        </div>
      </Card>
    </button>
  )
}

/** Today's reading momentum — real shelf numbers (streak / pages), no invented goal. */
function ReadingMomentum({ stats }: { stats: Shelf['stats'] }) {
  const cells: { label: string; value: number; icon: IconName }[] = [
    { label: 'kun ketma-ket', value: stats.streak, icon: 'flame' },
    { label: 'bet bugun', value: stats.today_pages, icon: 'book-open' },
    { label: 'bet bu hafta', value: stats.week_pages, icon: 'bar-chart' },
  ]
  return (
    <>
      <SectionTitle action={<button type="button" className="text-xs font-semibold text-brand-600 dark:text-brand-300" onClick={() => go('/shelf')}>Javonim</button>}>
        Bugungi mutolaa
      </SectionTitle>
      <Card tone="brand" className="grid grid-cols-3 gap-2 text-center">
        {cells.map((cell) => (
          <div key={cell.label} className="flex flex-col items-center gap-0.5">
            <Icon name={cell.icon} size={18} className="text-brand-600 dark:text-brand-300" />
            <span className="font-serif text-xl font-bold tabular-nums leading-none">{cell.value}</span>
            <span className="text-[11px] leading-tight text-app-hint">{cell.label}</span>
          </div>
        ))}
      </Card>
    </>
  )
}

const QUICK: { route: string; icon: IconName; label: string; tone: TileTone }[] = [
  { route: 'tests', icon: 'file-text', label: 'Testlar', tone: 'brand' },
  { route: 'checkin', icon: 'check-circle', label: 'Davomat', tone: 'green' },
  { route: 'results', icon: 'bar-chart', label: 'Natijalarim', tone: 'gold' },
]

export function HomePage() {
  const { me, api } = useAuth()
  // One request for the whole home (active book, next event, open test, live check-in). Points and the
  // reading streak are their own feature-gated calls.
  const { state, reload } = useAsync((signal) => api<HomeData>('/api/v1/me/home', { signal }))
  const ranking = useAsync((signal) => api<MyRanking>('/api/v1/me/ranking', { signal }))
  const shelfOn = me?.features?.shelf === 'on'
  const shelf = useAsync((signal) => (shelfOn ? api<Shelf>('/api/v1/me/shelf', { signal }) : Promise.resolve(null)), [shelfOn])
  if (!me) return null

  const home = state.status === 'success' ? state.data : null
  const current = home?.book ?? undefined
  const nextEvent = home?.event ?? undefined
  const openTest = home?.test ?? undefined
  const liveAttendance = home?.attendance && !home.attendance.checked_in ? home.attendance : undefined
  const points = ranking.state.status === 'success' ? ranking.state.data.all : null
  const stats = shelf.state.status === 'success' ? (shelf.state.data?.stats ?? null) : null

  return (
    <>
      {/* Hero: greeting + points. Navy-on-brand with the mark's gold four-point star and a gold points
          badge — a distinctive, premium first impression. */}
      <section className="relative overflow-hidden rounded-3xl bg-brand-gradient p-4 text-white shadow-[var(--shadow-brand)] ring-1 ring-white/10">
        <span aria-hidden className="pointer-events-none absolute -right-3 -top-6 select-none text-[6.5rem] leading-none text-gold-400/15">
          ✦
        </span>
        <div className="relative flex items-center gap-3">
          <span className="rounded-full ring-2 ring-gold-400/40">
            <Avatar me={me} size="size-12" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm text-white/75">Assalomu alaykum,</p>
            <h1 className="truncate font-serif text-xl font-bold">{me.first_name}!</h1>
          </div>
          {points && (
            <button
              type="button"
              onClick={() => go('/results')}
              className="flex flex-col items-center rounded-2xl bg-white/10 px-3.5 py-2 ring-1 ring-white/15 backdrop-blur active:scale-95"
            >
              <span className="text-xl font-bold leading-none tabular-nums text-gold-300">{points.total}</span>
              <span className="mt-0.5 text-[11px] text-white/75">ball · {points.rank}-o‘rin</span>
            </button>
          )}
        </div>
      </section>

      {/* Most time-sensitive action first: an open check-in. */}
      {liveAttendance && (
        <button type="button" className="w-full text-left" onClick={() => go('/checkin?scan=1')}>
          <Card interactive tone="brand" className="flex items-center gap-3">
            <FeatureTile icon="check-circle" tone="brand" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">Davomat ochiq!</p>
              <p className="truncate text-sm text-app-hint">«{liveAttendance.title}» — bosing va QR kodni skanerlang</p>
            </div>
            <Icon name="chevron-right" className="shrink-0 text-brand-600 dark:text-brand-300" />
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

      {stats && <ReadingMomentum stats={stats} />}

      {openTest && (
        <>
          <SectionTitle>Ochiq test</SectionTitle>
          <button type="button" className="w-full text-left" onClick={() => go(`/tests/${openTest.id}`)}>
            <Card interactive className="flex items-center gap-3">
              <FeatureTile icon="file-text" tone="gold" />
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{openTest.title}</p>
                <p className="truncate text-sm text-app-hint">
                  {openTest.in_progress ? 'Davom ettiring' : `${openTest.max_score} ballgacha`} · yopiladi{' '}
                  {formatEventDate(openTest.ends_at)}
                </p>
              </div>
              <Icon name="chevron-right" className="shrink-0 text-brand-600 dark:text-brand-300" />
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

      {/* A few everyday actions one tap away; everything else lives in «Barcha xizmatlar». */}
      <div className="grid grid-cols-3 gap-2.5">
        {QUICK.map((item) => (
          <button
            key={item.route}
            type="button"
            onClick={() => go(`/${item.route}`)}
            className="flex min-h-[88px] flex-col items-center justify-center gap-2 rounded-2xl border border-[color:var(--hairline)] bg-app-bg px-2 py-3 text-center text-xs font-medium shadow-[var(--shadow-card)] transition-transform active:scale-95"
          >
            <FeatureTile icon={item.icon} tone={item.tone} />
            {item.label}
          </button>
        ))}
      </div>

      <button type="button" className="w-full text-left" onClick={() => go('/services')}>
        <Card interactive className="flex items-center gap-3">
          <FeatureTile icon="grid" tone="hint" />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">Barcha xizmatlar</p>
            <p className="truncate text-sm text-app-hint">Javon, missiyalar, yutuqlar, sovg‘alar, premium va boshqalar</p>
          </div>
          <Icon name="chevron-right" className="shrink-0 text-app-hint" />
        </Card>
      </button>

      <BenefitCard />
    </>
  )
}
