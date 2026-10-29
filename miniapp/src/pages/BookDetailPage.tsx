import { useCallback, useState } from 'react'

import { BookCover } from '../components/BookCover'
import { Icon } from '../components/Icon'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import { useFeature } from '../components/FeatureGate'
import type { Book, BookDetail, Shelf, ShelfItem } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate } from '../utils/router'
import { confirmAction, haptic, openExternalLink } from '../utils/telegram'

export function BookDetailPage({ bookId }: { bookId: string }) {
  const { api } = useAuth()
  const { state, reload } = useAsync((signal) => api<BookDetail>(`/api/v1/books/${bookId}`, { signal }), [bookId])
  const [saving, setSaving] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const goBack = useCallback(() => navigate('/books'), [])
  useBackButton(goBack)
  const shelfOn = useFeature('shelf') === 'on'

  /** The book on «📚 Javonim» (added first when it is not there yet), then its page. */
  async function openOnShelf() {
    setSaving(true)
    setActionError(null)
    try {
      const shelf = await api<Shelf>('/api/v1/me/shelf')
      let item = shelf.items.find((entry) => entry.book_id === bookId)
      if (!item) item = await api<ShelfItem>('/api/v1/me/shelf', { method: 'POST', body: { book_id: bookId, status: 'READING' } })
      navigate(`/shelf/${item.id}`)
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : "Ochib bo'lmadi.")
    } finally {
      setSaving(false)
    }
  }

  async function setReading(action: 'start' | 'complete') {
    if (action === 'complete' && !(await confirmAction("Kitobni to'liq o'qib tugatdingizmi?"))) return
    setSaving(true)
    setActionError(null)
    try {
      await api<Book>(`/api/v1/books/${bookId}/reading`, { method: 'POST', body: { action } })
      haptic('success')
      reload()
    } catch (error) {
      haptic('error')
      setActionError(error instanceof ApiError ? error.message : "Saqlab bo'lmadi.")
    } finally {
      setSaving(false)
    }
  }

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const book = state.data
  const reading = book.my_reading
  const open = book.status === 'ACTIVE' || book.status === 'COMPLETED'
  const pastDeadline = Boolean(book.deadline && new Date(`${book.deadline}T23:59:59`) < new Date())

  return (
    <>
      <Card className="flex flex-col items-center gap-3 text-center">
        <BookCover url={book.cover_url} title={book.title} className="h-48 w-32 rounded-xl shadow-[var(--shadow-float)]" />
        <div>
          <h1 className="font-serif text-2xl font-bold leading-tight">{book.title}</h1>
          <p className="mt-0.5 text-app-hint">{book.author}</p>
        </div>
        <div className="flex flex-wrap justify-center gap-1.5 text-xs text-app-hint">
          {book.pages && (
            <span className="inline-flex items-center gap-1 rounded-full bg-app-surface px-2.5 py-1">
              <Icon name="file-text" size={13} />
              {book.pages} bet
            </span>
          )}
          {book.deadline && (
            <span className="inline-flex items-center gap-1 rounded-full bg-app-surface px-2.5 py-1">
              <Icon name="calendar" size={13} />
              {formatDate(book.deadline)}
            </span>
          )}
          <span className="inline-flex items-center gap-1 rounded-full bg-app-surface px-2.5 py-1">
            <Icon name="users" size={13} />
            {book.readers_count} o'quvchi
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-app-surface px-2.5 py-1">
            <Icon name="check" size={13} />
            {book.completed_count} tugatgan
          </span>
        </div>
      </Card>

      <Card className="flex flex-col gap-3">
        {book.source_url && (
          <Button variant="secondary" onClick={() => openExternalLink(book.source_url!)}>
            <Icon name="book-open" size={18} />Kitobni ochish
          </Button>
        )}
        {pastDeadline && reading?.status !== 'COMPLETED' && open && (
          <p className="text-center text-xs text-app-hint">
            <Icon name="clock" size={13} className="mr-1 inline align-[-2px]" />
            Muddat o'tgan. O'qib tugatsangiz ham bo'ladi — portfoliongizga qo'shiladi, faqat ball berilmaydi.
          </p>
        )}
        {!reading && open && (
          <Button loading={saving} onClick={() => setReading('start')}>
            O'qishni boshladim
          </Button>
        )}
        {reading?.status === 'READING' && (
          <Button loading={saving} onClick={() => setReading('complete')}>
            <Icon name="check" size={18} />O'qib tugatdim
          </Button>
        )}
        {reading?.status === 'COMPLETED' && (
          <div className="flex flex-col items-center gap-1 py-1 text-center">
            {reading.verified ? (
              <Badge tone="success"><Icon name="check" size={13} />O'qiganingiz tasdiqlangan</Badge>
            ) : (
              <>
                <Badge tone="success"><Icon name="check" size={13} />O'qib tugatdingiz</Badge>
                {reading.late ? (
                  <p className="text-xs text-app-hint">Muddatdan keyin o'qildi: portfolioga qo'shildi, ball berilmaydi.</p>
                ) : reading.verification_required && (
                  <p className="text-xs text-app-hint">
                    Kitob uchun ball test yoki muhokamada tasdiqlangandan keyin beriladi.
                  </p>
                )}
              </>
            )}
          </div>
        )}
        {shelfOn && open && (
          <Button variant="secondary" loading={saving} onClick={() => void openOnShelf()}>
            <Icon name="book-open" size={18} />Javonimda ochish: kundalik, 3 savol
          </Button>
        )}
        {actionError && (
          <p role="alert" className="text-center text-sm text-app-danger">
            {actionError}
          </p>
        )}
      </Card>

      {book.description && (
        <Card>
          <SectionTitle>Kitob haqida</SectionTitle>
          <p className="whitespace-pre-line text-[15px] leading-relaxed">{book.description}</p>
        </Card>
      )}

      {book.quotes.length > 0 && (
        <>
          <SectionTitle>Iqtiboslar</SectionTitle>
          {book.quotes.map((quote) => (
            <Card key={quote.id} className="border-l-2 border-l-gold-400">
              <blockquote className="font-serif text-[15px] italic leading-relaxed">«{quote.text}»</blockquote>
              <p className="mt-2 text-right text-sm text-app-hint">
                — {quote.author ?? book.author}
                {quote.source ? `, ${quote.source}` : ''}
              </p>
            </Card>
          ))}
        </>
      )}
    </>
  )
}
