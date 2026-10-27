import { useCallback, useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Card } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { useAuth } from '../store/auth'
import { navigate } from '../utils/router'

type Period = 'week' | 'month' | 'all'

interface LeagueRow {
  rank: number
  faculty: string
  members: number
  total: number
  average: number
  mine: boolean
  active: number
  participation: number
  pages: number
  books: number
  visits: number
}

const PERIODS: { value: Period; label: string }[] = [
  { value: 'week', label: 'Hafta' },
  { value: 'month', label: 'Oy' },
  { value: 'all', label: 'Umumiy' },
]
const MEDALS = ['🥇', '🥈', '🥉']

/** «🏛 Fakultetlar ligasi»: the faculties as teams — average points per member decide the place. */
export function LeaguePage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/ranking'), [])
  useBackButton(goBack)
  const [period, setPeriod] = useState<Period>('month')
  const { state, reload } = useAsync(
    (signal) => api<{ items: LeagueRow[] }>(`/api/v1/league?period=${period}`, { signal }),
    [period],
  )

  return (
    <div className="flex flex-col gap-3">
      <div className="px-1">
        <h1 className="font-serif text-2xl font-bold">🏛 Fakultetlar ligasi</h1>
        <p className="text-sm text-app-hint">
          O‘rin — fakultet a’zolarining o‘rtacha bali bo‘yicha (katta-kichik fakultetlar teng). Har bir o‘qigan betingiz fakultetingizni oldinga
          suradi!
        </p>
      </div>
      <div className="grid grid-cols-3 gap-1 rounded-xl bg-app-surface p-1">
        {PERIODS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setPeriod(item.value)}
            className={`rounded-lg py-1.5 text-sm font-medium transition-colors ${period === item.value ? 'bg-brand-500 text-white' : 'text-app-hint'}`}
          >
            {item.label}
          </button>
        ))}
      </div>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.items.length === 0 && (
        <Card>
          <EmptyState icon="🏛" title="Fakultetlar hali qo‘shilmagan" />
        </Card>
      )}
      {state.status === 'success' &&
        state.data.items.map((row) => (
          <Card key={row.faculty} className={`flex flex-col gap-2 ${row.mine ? 'ring-2 ring-brand-500' : ''}`}>
            <div className="flex items-center gap-3">
              <span className="w-8 shrink-0 text-center text-xl font-semibold tabular-nums">
                {row.rank <= 3 ? MEDALS[row.rank - 1] : row.rank}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold leading-snug">
                  {row.faculty}
                  {row.mine && <span className="ml-1 text-xs text-app-link">(sizning fakultetingiz)</span>}
                </p>
                <p className="text-xs text-app-hint">
                  {row.members} a’zo · faol {row.active} ({row.participation}%)
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="text-lg font-semibold tabular-nums">{row.average}</p>
                <p className="text-[11px] text-app-hint">o‘rtacha ball</p>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-1 text-center text-xs">
              <div className="rounded-lg bg-app-surface py-1.5">
                <p className="font-semibold tabular-nums">{row.total.toLocaleString('uz-UZ')}</p>
                <p className="text-app-hint">ball</p>
              </div>
              <div className="rounded-lg bg-app-surface py-1.5">
                <p className="font-semibold tabular-nums">{row.pages.toLocaleString('uz-UZ')}</p>
                <p className="text-app-hint">bet</p>
              </div>
              <div className="rounded-lg bg-app-surface py-1.5">
                <p className="font-semibold tabular-nums">{row.books}</p>
                <p className="text-app-hint">kitob</p>
              </div>
              <div className="rounded-lg bg-app-surface py-1.5">
                <p className="font-semibold tabular-nums">{row.visits}</p>
                <p className="text-app-hint">tadbir</p>
              </div>
            </div>
          </Card>
        ))}
    </div>
  )
}
