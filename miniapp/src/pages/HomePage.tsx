import { BookCover } from '../components/BookCover'
import { Avatar } from '../components/Avatar'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { Book, Page } from '../types/api'
import { daysUntil, formatDate } from '../utils/format'
import { navigate } from '../utils/router'

const SHORTCUTS = [
  { route: 'books', icon: '📚', label: 'Kitoblar' },
  { route: 'events', icon: '📅', label: 'Tadbirlar' },
  { route: 'tests', icon: '📝', label: 'Testlar' },
  { route: 'results', icon: '📊', label: 'Natijalarim' },
  { route: 'achievements', icon: '🏅', label: 'Yutuqlar' },
  { route: 'ranking', icon: '🏆', label: 'Reyting' },
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
      </Card>

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

      <SectionTitle>Bo'limlar</SectionTitle>
      <div className="grid grid-cols-3 gap-2">
        {SHORTCUTS.map((item) => (
          <button
            key={item.route}
            type="button"
            onClick={() => navigate(`/${item.route}`)}
            className="flex flex-col items-center gap-1 rounded-2xl bg-app-bg px-2 py-4 text-sm shadow-sm active:opacity-70"
          >
            <span aria-hidden className="text-2xl">
              {item.icon}
            </span>
            {item.label}
          </button>
        ))}
      </div>
    </>
  )
}
