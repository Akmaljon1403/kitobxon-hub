import { useState } from 'react'

import { BookCover } from '../components/BookCover'
import { Icon } from '../components/Icon'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, PageTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Book, MyBookSuggestion, Page } from '../types/api'
import { formatDate } from '../utils/format'
import { useHomeBackButton } from '../hooks/useBackButton'
import { navigate } from '../utils/router'
import { LibrarySwitch } from './ShelfPage'

const inputClass = 'rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none transition focus:ring-2 focus:ring-brand-400/50'
const SUGGESTION_BADGE: Record<string, { label: string; tone: 'info' | 'success' | 'danger' | 'neutral' }> = {
  SUGGESTED: { label: 'Ko‘rib chiqilmoqda', tone: 'info' },
  ACTIVE: { label: 'Qo‘shildi', tone: 'success' },
  COMPLETED: { label: 'Qo‘shildi', tone: 'success' },
  REJECTED: { label: 'Qo‘shilmadi', tone: 'danger' },
}

/** Members propose a book for the club library; an admin then publishes or rejects it. */
function SuggestBook({ onChanged }: { onChanged: () => void }) {
  const { api } = useAuth()
  const mine = useAsync((signal) => api<MyBookSuggestion[]>('/api/v1/books/suggestions', { signal }))
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [source, setSource] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      await api('/api/v1/books/suggestions', {
        method: 'POST',
        body: { title: title.trim(), author: author.trim(), source_url: source.trim() || null },
      })
      setTitle('')
      setAuthor('')
      setSource('')
      setOpen(false)
      mine.reload()
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi")
    } finally {
      setBusy(false)
    }
  }

  const suggestions = mine.state.status === 'success' ? mine.state.data : []
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 font-semibold">
          <Icon name="lightbulb" size={16} />Kitob taklif qilish
        </p>
        {!open && (
          <Button variant="secondary" className="w-auto shrink-0 px-3 py-1.5 text-sm" onClick={() => setOpen(true)}>
            <Icon name="plus" size={16} />Taklif
          </Button>
        )}
      </div>
      {!open && (
        <p className="text-sm text-app-hint">Klub kutubxonasiga qo‘shilishini istagan kitobingizni taklif qiling — adminlar ko‘rib chiqadi.</p>
      )}
      {open && (
        <>
          <input className={inputClass} placeholder="Kitob nomi" value={title} maxLength={255} onChange={(e) => setTitle(e.target.value)} />
          <input className={inputClass} placeholder="Muallif" value={author} maxLength={255} onChange={(e) => setAuthor(e.target.value)} />
          <input
            className={inputClass}
            placeholder="Havola (ixtiyoriy): https://…"
            value={source}
            inputMode="url"
            onChange={(e) => setSource(e.target.value)}
          />
          {error && <p className="text-sm text-app-danger">{error}</p>}
          <div className="grid grid-cols-2 gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Bekor
            </Button>
            <Button loading={busy} disabled={!title.trim() || !author.trim()} onClick={() => void submit()}>
              Yuborish
            </Button>
          </div>
        </>
      )}
      {suggestions.length > 0 && (
        <div className="flex flex-col gap-1.5 border-t border-app-border pt-2">
          <p className="text-xs font-medium text-app-hint">Mening takliflarim</p>
          {suggestions.map((s) => {
            const badge = SUGGESTION_BADGE[s.status] ?? SUGGESTION_BADGE.SUGGESTED
            return (
              <div key={s.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="min-w-0 truncate">
                  {s.title} <span className="text-app-hint">— {s.author}</span>
                </span>
                <Badge tone={badge.tone}>{badge.label}</Badge>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

export function ReadingBadge({ book }: { book: Book }) {
  if (!book.my_reading) return null
  if (book.my_reading.status === 'READING') return <Badge tone="info"><Icon name="book-open" size={13} />O'qiyapman</Badge>
  if (book.my_reading.verified) return <Badge tone="success"><Icon name="check" size={13} />Tasdiqlangan</Badge>
  return <Badge tone="success"><Icon name="check" size={13} />O'qib tugatdim</Badge>
}

export function BooksPage() {
  useHomeBackButton()
  const { api, me } = useAuth()
  const { state, reload } = useAsync((signal) => api<Page<Book>>('/api/v1/books?limit=100', { signal }))

  const shelf = me?.features?.shelf === 'on'
  return (
    <>
      {shelf && <LibrarySwitch current="books" />}
      <PageTitle icon={shelf ? 'landmark' : 'book'}>{shelf ? 'Klub kitoblari' : 'Kitoblar'}</PageTitle>
      {shelf && (
        <p className="-mt-2 px-1 text-sm text-app-hint">Klub tavsiya qilgan kitoblar — yoqqanini «Javonim»ga qo‘shing.</p>
      )}
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.items.length === 0 && (
        <EmptyState title="Hozircha kitob yo'q">Klub rahbariyati yangi kitob qo'shganda shu yerda ko'rinadi.</EmptyState>
      )}
      <SuggestBook onChanged={reload} />
      {state.status === 'success' &&
        state.data.items.map((book) => (
          <button key={book.id} type="button" className="text-left" onClick={() => navigate(`/books/${book.id}`)}>
            <Card interactive className="flex gap-3">
              <BookCover url={book.cover_url} title={book.title} className="h-24 w-16 shrink-0 rounded-lg shadow-[var(--shadow-card)]" />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="line-clamp-2 font-serif text-lg font-bold leading-snug">{book.title}</h2>
                  {book.status === 'COMPLETED' && <Badge>Yakunlangan</Badge>}
                </div>
                <p className="truncate text-sm text-app-hint">{book.author}</p>
                {book.deadline && <p className="text-xs text-app-hint">Muddat: {formatDate(book.deadline)}</p>}
                <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
                  <ReadingBadge book={book} />
                  {book.completed_count > 0 && (
                    <span className="text-xs text-app-hint">{book.completed_count} kishi o'qib tugatdi</span>
                  )}
                </div>
              </div>
            </Card>
          </button>
        ))}
    </>
  )
}
