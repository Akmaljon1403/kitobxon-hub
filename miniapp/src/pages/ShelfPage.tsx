import { useCallback, useMemo, useState } from 'react'

import { BookCover } from '../components/BookCover'
import { Icon, type IconName } from '../components/Icon'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, PageTitle, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Book, Page, ReadingStats, Shelf, ShelfItem, ShelfStatus } from '../types/api'
import { navigate } from '../utils/router'
import { haptic } from '../utils/telegram'

export const STATUS_TITLES: Record<ShelfStatus, string> = {
  READING: "O'qiyapman",
  WANT: "O'qimoqchiman",
  FINISHED: "O'qib bo'ldim",
  LATER: 'Keyinroq',
}
export const STATUS_ICONS: Record<ShelfStatus, IconName> = {
  READING: 'book-open',
  WANT: 'bookmark',
  FINISHED: 'check',
  LATER: 'hourglass',
}
const TABS: ShelfStatus[] = ['READING', 'WANT', 'FINISHED', 'LATER']

export function ProgressBar({ percent }: { percent: number | null }) {
  if (percent === null) return null
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-app-surface" aria-label={`${percent}%`}>
      <div className="h-full rounded-full bg-brand-gradient transition-all" style={{ width: `${Math.max(3, percent)}%` }} />
    </div>
  )
}

/** The last 14 days as small bars (pages a day); today is the last one. */
function DaysChart({ stats }: { stats: ReadingStats }) {
  const max = Math.max(1, ...stats.last_days.map((day) => day.pages))
  return (
    <div className="flex h-14 items-end gap-1" aria-label="Oxirgi 14 kun">
      {stats.last_days.map((day, index) => (
        <div key={day.date} className="flex flex-1 flex-col items-center justify-end">
          <div
            title={`${day.date}: ${day.pages} bet`}
            className={`w-full rounded-t ${index === stats.last_days.length - 1 ? 'bg-brand-500 dark:bg-brand-400' : 'bg-brand-500/40'}`}
            style={{ height: `${day.pages ? Math.max(8, (day.pages / max) * 100) : 4}%`, opacity: day.pages ? 1 : 0.35 }}
          />
        </div>
      ))}
    </div>
  )
}

function StatsCard({ stats }: { stats: ReadingStats }) {
  return (
    <Card className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="flex items-center justify-center gap-1 text-2xl font-semibold tabular-nums">
            <Icon name="flame" size={20} className="text-gold-500 dark:text-gold-300" />
            {stats.streak}
          </p>
          <p className="text-xs text-app-hint">kun ketma-ket</p>
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums">{stats.week_pages}</p>
          <p className="text-xs text-app-hint">bet bu hafta</p>
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums">{stats.finished_this_year}</p>
          <p className="text-xs text-app-hint">kitob bu yil</p>
        </div>
      </div>
      <DaysChart stats={stats} />
      <p className="text-center text-xs text-app-hint">
        Bugun: <b>{stats.today_pages}</b> bet · eng uzun seriya: {stats.best_streak} kun · yil davomida {stats.year_pages} bet
      </p>
    </Card>
  )
}

/** Quick «+ N bet» for a book being read, right on the shelf. */
function QuickLog({ item, onDone }: { item: ShelfItem; onDone: () => void }) {
  const { api } = useAuth()
  const [pages, setPages] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    const value = Number(pages)
    if (!Number.isInteger(value) || value <= 0) {
      setError('Betlar sonini yozing')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api(`/api/v1/me/shelf/${item.id}/logs`, { method: 'POST', body: { pages: value } })
      haptic('success')
      setPages('')
      onDone()
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex gap-2">
        <input
          type="number"
          inputMode="numeric"
          min={1}
          placeholder="Bugun necha bet?"
          value={pages}
          onChange={(event) => setPages(event.target.value)}
          className="min-w-0 flex-1 rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none transition focus:ring-2 focus:ring-brand-400/50"
        />
        <Button className="w-auto shrink-0 px-4" loading={busy} onClick={() => void save()}>
          + Yozish
        </Button>
      </div>
      {error && <p className="text-xs text-app-danger">{error}</p>}
    </div>
  )
}

function ItemCard({ item, onChange }: { item: ShelfItem; onChange: () => void }) {
  return (
    <Card className="flex flex-col gap-3">
      <button type="button" className="flex items-start gap-3 text-left" onClick={() => navigate(`/shelf/${item.id}`)}>
        <BookCover url={item.cover_url} title={item.title} className="h-20 w-14 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold leading-snug">{item.title}</p>
          {item.author && <p className="text-sm text-app-hint">{item.author}</p>}
          <p className="mt-1 text-xs text-app-hint">
            {item.pages_total ? `${item.pages_read}/${item.pages_total} bet` : `${item.pages_read} bet o'qildi`}
            {item.club_book && ' · klub kitobi'}
            {item.rating ? ` · ${'★'.repeat(item.rating)}` : ''}
          </p>
          <div className="mt-2">
            <ProgressBar percent={item.percent} />
          </div>
        </div>
        <Icon name="chevron-right" size={18} className="shrink-0 self-center text-app-hint" />
      </button>
      {item.status === 'READING' && <QuickLog item={item} onDone={onChange} />}
    </Card>
  )
}

/** Add a club book (search) or a book of one's own. */
function AddBook({ onAdded, existing }: { onAdded: () => void; existing: Set<string> }) {
  const { api } = useAuth()
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [pages, setPages] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const club = useAsync((signal) => (open ? api<Page<Book>>('/api/v1/books?limit=100', { signal }) : Promise.resolve(null)), [open])

  async function add(body: Record<string, unknown>, key: string) {
    setBusy(key)
    setError(null)
    try {
      await api('/api/v1/me/shelf', { method: 'POST', body })
      haptic('success')
      setTitle('')
      setAuthor('')
      setPages('')
      setOpen(false)
      onAdded()
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : "Qo'shib bo'lmadi")
    } finally {
      setBusy(null)
    }
  }

  if (!open) {
    return (
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <Icon name="plus" size={18} />Kitob qo'shish
      </Button>
    )
  }
  const books = club.state.status === 'success' && club.state.data ? club.state.data.items.filter((book) => !existing.has(book.id)) : []
  return (
    <Card className="flex flex-col gap-3">
      <p className="flex items-center gap-1.5 font-semibold"><Icon name="plus" size={16} />Javonga kitob qo'shish</p>
      {books.length > 0 && (
        <>
          <p className="text-sm text-app-hint">Klub kitoblaridan:</p>
          <div className="flex max-h-56 flex-col gap-1 overflow-y-auto">
            {books.map((book) => (
              <button
                key={book.id}
                type="button"
                disabled={busy !== null}
                onClick={() => void add({ book_id: book.id, status: 'WANT' }, book.id)}
                className="flex items-center justify-between gap-2 rounded-xl bg-app-surface px-3 py-2 text-left text-sm"
              >
                <span className="min-w-0 truncate">
                  {book.title} <span className="text-app-hint">— {book.author}</span>
                </span>
                <span className="shrink-0 text-app-link">{busy === book.id ? '…' : '＋'}</span>
              </button>
            ))}
          </div>
        </>
      )}
      <p className="text-sm text-app-hint">Yoki o'zingizning kitobingiz:</p>
      <input
        placeholder="Kitob nomi"
        value={title}
        maxLength={255}
        onChange={(event) => setTitle(event.target.value)}
        className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none transition focus:ring-2 focus:ring-brand-400/50"
      />
      <div className="flex gap-2">
        <input
          placeholder="Muallif"
          value={author}
          maxLength={255}
          onChange={(event) => setAuthor(event.target.value)}
          className="min-w-0 flex-1 rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none transition focus:ring-2 focus:ring-brand-400/50"
        />
        <input
          type="number"
          inputMode="numeric"
          placeholder="Betlar"
          value={pages}
          onChange={(event) => setPages(event.target.value)}
          className="w-24 rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none transition focus:ring-2 focus:ring-brand-400/50"
        />
      </div>
      {error && <p className="text-sm text-app-danger">{error}</p>}
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" onClick={() => setOpen(false)}>
          Bekor
        </Button>
        <Button
          loading={busy === 'own'}
          disabled={!title.trim()}
          onClick={() =>
            void add({ title, author: author || null, pages_total: Number(pages) > 0 ? Number(pages) : null, status: 'READING' }, 'own')
          }
        >
          Qo'shish
        </Button>
      </div>
    </Card>
  )
}

/** «📚 Javonim»: my books by status, the reading diary numbers and a quick «+ bet». */
/** «📚 Javonim | 🏛 Klub kitoblari» — the two halves of the library tab. */
export function LibrarySwitch({ current }: { current: 'shelf' | 'books' }) {
  const items: { code: 'shelf' | 'books'; icon: IconName; label: string }[] = [
    { code: 'shelf', icon: 'bookmark', label: 'Javonim' },
    { code: 'books', icon: 'landmark', label: 'Klub kitoblari' },
  ]
  return (
    <div className="grid grid-cols-2 gap-1 rounded-2xl bg-app-surface p-1">
      {items.map((item) => (
        <button
          key={item.code}
          type="button"
          onClick={() => current !== item.code && navigate(`/${item.code}`)}
          aria-current={current === item.code ? 'page' : undefined}
          className={`flex items-center justify-center gap-1.5 rounded-xl py-2 text-sm font-medium ${current === item.code ? 'bg-app-bg shadow-sm' : 'text-app-hint'}`}
        >
          <Icon name={item.icon} size={15} />
          {item.label}
        </button>
      ))}
    </div>
  )
}

export function ShelfPage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<Shelf>('/api/v1/me/shelf', { signal }))
  const [tab, setTab] = useState<ShelfStatus>('READING')
  const existing = useMemo(
    () => new Set(state.status === 'success' ? state.data.items.map((item) => item.book_id).filter((id): id is string => Boolean(id)) : []),
    [state],
  )

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const { items, stats } = state.data
  const shown = items.filter((item) => item.status === tab)

  return (
    <div className="flex flex-col gap-3">
      <LibrarySwitch current="shelf" />
      <div>
        <PageTitle icon="bookmark">Javonim</PageTitle>
        <p className="px-1 text-sm text-app-hint">Kitoblaringiz, mutolaa kundaligi va seriyangiz</p>
      </div>
      <StatsCard stats={stats} />
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" onClick={() => navigate('/missions')}>
          <Icon name="target" size={18} />Missiyalar
        </Button>
        <Button variant="secondary" onClick={() => navigate('/quotes')}>
          <Icon name="quote" size={18} />Iqtiboslarim ({stats.quotes})
        </Button>
      </div>
      <div className="flex gap-1 overflow-x-auto pb-1">
        {TABS.map((status) => (
          <button
            key={status}
            type="button"
            onClick={() => setTab(status)}
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${tab === status ? 'bg-brand-500 text-white' : 'bg-app-surface text-app-hint'}`}
          >
            <Icon name={STATUS_ICONS[status]} size={14} />
            {STATUS_TITLES[status]}
            {stats.shelf[status] ? ` · ${stats.shelf[status]}` : ''}
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <Card>
          <EmptyState icon="bookmark" title="Bu javon hozircha bo'sh">
            {tab === 'READING' ? "Kitob qo'shing va har kuni o'qigan betlaringizni yozib boring — seriyangiz o'sadi." : null}
          </EmptyState>
        </Card>
      ) : (
        shown.map((item) => <ItemCard key={item.id} item={item} onChange={reload} />)
      )}
      <AddBook onAdded={reload} existing={existing} />
      <SectionTitle>Botda ham</SectionTitle>
      <Card className="text-sm text-app-hint">
        Botga <b>/oqidim 25</b> deb yozsangiz, «O'qiyapman»dagi kitobingizga 25 bet qo'shiladi. <b>/javonim</b> — qisqacha holat,{' '}
        <b>/kartam</b> — kitobxonlik kartangiz rasmi.
      </Card>
    </div>
  )
}
