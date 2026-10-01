import { useCallback, useState } from 'react'

import { BookCover } from '../components/BookCover'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Book, BookDetail } from '../types/api'
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

  return (
    <>
      <Card className="flex flex-col items-center gap-3 text-center">
        <BookCover url={book.cover_url} title={book.title} className="h-48 w-32" />
        <div>
          <h1 className="text-xl font-semibold">{book.title}</h1>
          <p className="text-app-hint">{book.author}</p>
        </div>
        <div className="flex flex-wrap justify-center gap-2 text-xs text-app-hint">
          {book.pages && <span>📄 {book.pages} bet</span>}
          {book.deadline && <span>🗓 Muddat: {formatDate(book.deadline)}</span>}
          <span>
            👥 {book.readers_count} o'quvchi · {book.completed_count} tugatgan
          </span>
        </div>
      </Card>

      <Card className="flex flex-col gap-3">
        {book.source_url && (
          <Button variant="secondary" onClick={() => openExternalLink(book.source_url!)}>
            📖 Kitobni ochish
          </Button>
        )}
        {!reading && book.status === 'ACTIVE' && (
          <Button loading={saving} onClick={() => setReading('start')}>
            O'qishni boshladim
          </Button>
        )}
        {reading?.status === 'READING' && (
          <Button loading={saving} onClick={() => setReading('complete')}>
            ✓ O'qib tugatdim
          </Button>
        )}
        {reading?.status === 'COMPLETED' && (
          <div className="flex flex-col items-center gap-1 py-1 text-center">
            {reading.verified ? (
              <Badge tone="success">✅ O'qiganingiz tasdiqlangan</Badge>
            ) : (
              <>
                <Badge tone="success">✓ O'qib tugatdingiz</Badge>
                {reading.verification_required && (
                  <p className="text-xs text-app-hint">
                    Kitob uchun ball test yoki muhokamada tasdiqlangandan keyin beriladi.
                  </p>
                )}
              </>
            )}
          </div>
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
            <Card key={quote.id}>
              <blockquote className="text-[15px] italic leading-relaxed">«{quote.text}»</blockquote>
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
