import { Badge } from './ui'
import { ErrorState, LoadingState } from './StateViews'
import { useAsync } from '../hooks/useAsync'
import { useSession } from '../store/session'
import { formatDate } from '../utils/format'

export interface ScoreHistoryItem {
  id: string
  amount: number
  category: string
  category_label: string
  reason: string | null
  created_at: string
  by: string | null
}

/** The point-history rows for one member: when, why (category + reason), who gave it, and how many points. */
export function ScoreHistoryList({ items }: { items: ScoreHistoryItem[] }) {
  if (items.length === 0) return <p className="text-xs text-app-hint">Hali ball berilmagan.</p>
  return (
    <ul className="flex flex-col gap-1.5">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-start justify-between gap-3 border-b border-app-border/60 pb-1.5 text-sm last:border-0"
        >
          <div className="min-w-0">
            <span className="text-app-hint">{formatDate(item.created_at)}</span>{' '}
            <Badge tone="neutral">{item.category_label}</Badge>
            {item.reason && <span className="ml-1 break-words text-app-text">— {item.reason}</span>}
            {item.by && <span className="ml-1 text-xs text-app-hint">({item.by})</span>}
          </div>
          <span
            className={`shrink-0 font-semibold tabular-nums ${item.amount > 0 ? 'text-emerald-600' : 'text-app-danger'}`}
          >
            {item.amount > 0 ? `+${item.amount}` : item.amount}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** «🧾 Ball tarixi»: har bir ball a'zoga nima uchun berilgani — sana, sabab, miqdor, kim bergani.
 *  Members modalida yopiq (collapsible), audit jurnalida ochiq ko'rinadi. */
export function MemberScoreHistory({ userId, open = false }: { userId: string; open?: boolean }) {
  const { api } = useSession()
  const { state } = useAsync(
    (signal) =>
      api<{ total: number; items: ScoreHistoryItem[] }>(`/api/v1/admin/users/${userId}/score-history?limit=100`, {
        signal,
      }),
    [userId],
  )
  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} />
  const { total, items } = state.data
  return (
    <details open={open} className="rounded-lg border border-app-border p-3">
      <summary className="cursor-pointer text-sm font-medium">
        🧾 Ball tarixi — har bir ball nega berilgani ({total})
      </summary>
      <div className="mt-2">
        <ScoreHistoryList items={items} />
      </div>
    </details>
  )
}
