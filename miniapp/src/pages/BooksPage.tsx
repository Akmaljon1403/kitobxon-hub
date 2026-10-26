import { BookCover } from '../components/BookCover'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Card } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { Book, Page } from '../types/api'
import { formatDate } from '../utils/format'
import { useHomeBackButton } from '../hooks/useBackButton'
import { navigate } from '../utils/router'
import { LibrarySwitch } from './ShelfPage'

export function ReadingBadge({ book }: { book: Book }) {
  if (!book.my_reading) return null
  if (book.my_reading.status === 'READING') return <Badge tone="info">📖 O'qiyapman</Badge>
  if (book.my_reading.verified) return <Badge tone="success">✅ Tasdiqlangan</Badge>
  return <Badge tone="success">✓ O'qib tugatdim</Badge>
}

export function BooksPage() {
  useHomeBackButton()
  const { api, me } = useAuth()
  const { state, reload } = useAsync((signal) => api<Page<Book>>('/api/v1/books?limit=100', { signal }))

  const shelf = me?.features?.shelf === 'on'
  return (
    <>
      {shelf && <LibrarySwitch current="books" />}
      <h1 className="px-1 pt-1 font-serif text-2xl font-bold">{shelf ? '🏛 Klub kitoblari' : '📚 Kitoblar'}</h1>
      {shelf && (
        <p className="-mt-2 px-1 text-sm text-app-hint">Klub tavsiya qilgan kitoblar — yoqqanini «Javonim»ga qo‘shing.</p>
      )}
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.items.length === 0 && (
        <EmptyState title="Hozircha kitob yo'q">Klub rahbariyati yangi kitob qo'shganda shu yerda ko'rinadi.</EmptyState>
      )}
      {state.status === 'success' &&
        state.data.items.map((book) => (
          <button key={book.id} type="button" className="text-left" onClick={() => navigate(`/books/${book.id}`)}>
            <Card className="flex gap-3">
              <BookCover url={book.cover_url} title={book.title} className="h-24 w-16 shrink-0" />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="line-clamp-2 font-semibold">{book.title}</h2>
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
