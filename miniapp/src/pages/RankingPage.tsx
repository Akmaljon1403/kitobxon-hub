import { useState } from 'react'

import { FeatureLocked, TrialBadge, useFeature } from '../components/FeatureGate'
import { Icon } from '../components/Icon'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Card, FeatureTile, PageTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { FacultyRanking, Ranking, RankingRow } from '../types/api'
import { useHomeBackButton } from '../hooks/useBackButton'
import { navigate } from '../utils/router'

type Period = 'week' | 'month' | 'all'
type Scope = 'all' | 'faculty' | 'group' | 'faculties'

const PERIODS: { value: Period; label: string }[] = [
  { value: 'week', label: 'Hafta' },
  { value: 'month', label: 'Oy' },
  { value: 'all', label: 'Umumiy' },
]
const SCOPES: { value: Scope; label: string }[] = [
  { value: 'all', label: 'Hammasi' },
  { value: 'faculty', label: 'Fakultetim' },
  { value: 'group', label: 'Guruhim' },
  { value: 'faculties', label: 'Fakultetlar' },
]
const MEDALS = ['🥇', '🥈', '🥉']

function Place({ rank }: { rank: number }) {
  return (
    <span className="w-8 shrink-0 text-center text-lg font-semibold tabular-nums">
      {rank <= 3 ? MEDALS[rank - 1] : rank}
    </span>
  )
}

/** The top three as a gold/silver/bronze podium — the first thing seen on the leaderboard. */
const PODIUM: Record<1 | 2 | 3, { tile: string; pedestal: string; order: string }> = {
  1: { tile: 'from-gold-300/50 to-gold-500/20 ring-gold-400/50', pedestal: 'h-16', order: 'order-2' },
  2: { tile: 'from-slate-200/70 to-slate-400/25 ring-slate-300/60', pedestal: 'h-12', order: 'order-1' },
  3: { tile: 'from-amber-200/60 to-amber-500/25 ring-amber-400/50', pedestal: 'h-10', order: 'order-3' },
}

function Podium({ top }: { top: RankingRow[] }) {
  return (
    <div className="flex items-end justify-center gap-2 px-2 pt-1">
      {top.map((row) => {
        const p = PODIUM[row.rank as 1 | 2 | 3] ?? PODIUM[3]
        return (
          <div key={`${row.rank}-${row.name}`} className={`flex min-w-0 flex-1 flex-col items-center ${p.order}`}>
            <span className={`mb-1 grid size-12 place-items-center rounded-full bg-gradient-to-b text-2xl ring-2 ${p.tile}`}>
              {MEDALS[row.rank - 1]}
            </span>
            <p className={`w-full truncate text-center text-xs ${row.is_me ? 'font-bold text-brand-600 dark:text-brand-300' : 'font-medium'}`}>
              {row.name}
              {row.is_me ? ' (siz)' : ''}
            </p>
            <p className="text-sm font-bold tabular-nums">{row.total}</p>
            <div className={`mt-1 w-full rounded-t-xl bg-brand-500/10 ${p.pedestal}`} />
          </div>
        )
      })}
    </div>
  )
}

function Row({ row }: { row: RankingRow }) {
  return (
    <li className={`flex items-center gap-3 px-3 py-2.5 ${row.is_me ? 'rounded-xl bg-brand-500/10' : ''}`}>
      <Place rank={row.rank} />
      <div className="min-w-0 flex-1">
        <p className={`truncate ${row.is_me ? 'font-semibold' : 'font-medium'}`}>
          {row.name}
          {row.premium && (
            <span aria-label="Premium a'zo" title="Premium a'zo" className="ml-0.5 inline-flex align-[-2px]">
              <Icon name="gem" size={13} className="text-gold-500 dark:text-gold-300" />
            </span>
          )}
          {row.is_me && ' (siz)'}
        </p>
        <p className="truncate text-xs text-app-hint">
          {[row.faculty, row.group_name].filter(Boolean).join(' · ')}
        </p>
      </div>
      <span className="font-semibold tabular-nums">{row.total}</span>
    </li>
  )
}

function Segmented<T extends string>({
  options,
  value,
  onChange,
  locked = [],
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
  locked?: T[]
}) {
  return (
    <div className="grid gap-1 rounded-2xl bg-app-surface p-1" style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }} role="tablist">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={value === option.value}
          onClick={() => onChange(option.value)}
          className={`truncate rounded-lg px-1 py-2 text-[13px] font-medium ${value === option.value ? 'bg-brand-500 text-white' : 'text-app-hint'}`}
        >
          {option.label}
          {locked.includes(option.value) && <Icon name="gem" size={12} className="ml-1 inline align-[-1px]" />}
        </button>
      ))}
    </div>
  )
}

function Leaderboard({ period, scope }: { period: Period; scope: Exclude<Scope, 'faculties'> }) {
  const { api } = useAuth()
  const { state, reload } = useAsync(
    (signal) => api<Ranking>(`/api/v1/rankings?period=${period}&scope=${scope}&limit=50`, { signal }),
    [period, scope],
  )
  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const { items, me } = state.data
  const meVisible = items.some((row) => row.is_me)
  const hasPodium = items.length >= 3
  const rest = hasPodium ? items.slice(3) : items
  return (
    <>
      <Card className="flex items-center justify-between">
        <div>
          <p className="text-sm text-app-hint">Sizning o'rningiz</p>
          <p className="text-2xl font-semibold">{me ? `${me.rank}-o'rin` : '—'}</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-app-hint">Ballaringiz</p>
          <p className="text-2xl font-semibold tabular-nums">{me?.total ?? 0}</p>
        </div>
      </Card>
      {items.length === 0 ? (
        <EmptyState icon="trophy" title="Hali ball to'plaganlar yo'q">
          Tadbirlarda qatnashing va testlarni ishlang — ismingiz shu yerda chiqadi.
        </EmptyState>
      ) : (
        <>
          {hasPodium && (
            <Card className="pb-1 pt-3">
              <Podium top={items.slice(0, 3)} />
            </Card>
          )}
          {(rest.length > 0 || (me && !meVisible)) && (
            <Card className="p-1">
              <ol>
                {rest.map((row) => (
                  <Row key={`${row.rank}-${row.name}`} row={row} />
                ))}
              </ol>
              {me && !meVisible && (
                <ol className="mt-1 border-t border-app-hint/15 pt-1">
                  <Row row={me} />
                </ol>
              )}
            </Card>
          )}
        </>
      )}
    </>
  )
}

function FacultyBoard({ period }: { period: Period }) {
  const { api } = useAuth()
  const { state, reload } = useAsync(
    (signal) => api<FacultyRanking[]>(`/api/v1/rankings/faculties?period=${period}`, { signal }),
    [period],
  )
  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  return (
    <Card className="p-1">
      <ol>
        {state.data.map((row) => (
          <li key={row.faculty} className="flex items-center gap-3 px-3 py-2.5">
            <Place rank={row.rank} />
            <div className="min-w-0 flex-1">
              <p className="font-medium">{row.faculty}</p>
              <p className="text-xs text-app-hint">
                {row.members} a'zo · jami {row.total} ball
              </p>
            </div>
            <div className="text-right">
              <p className="font-semibold tabular-nums">{row.average}</p>
              <p className="text-[10px] text-app-hint">o'rtacha</p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}

export function RankingPage() {
  useHomeBackButton()
  const [period, setPeriod] = useState<Period>('week')
  const [scope, setScope] = useState<Scope>('all')
  // This week's club-wide ranking is free; the other tabs are the «ranking_full» feature.
  const full = useFeature('ranking_full')
  const league = useFeature('faculty_league')
  const periods = full === 'off' ? PERIODS.filter((p) => p.value === 'week') : PERIODS
  const scopes = full === 'off' ? SCOPES.filter((s) => s.value === 'all') : SCOPES
  const isFree = period === 'week' && scope === 'all'
  return (
    <>
      <PageTitle icon="trophy" action={<TrialBadge code="ranking_full" />}>
        Reyting
      </PageTitle>
      {periods.length > 1 && (
        <Segmented options={periods} value={period} onChange={setPeriod} locked={full === 'premium' ? ['month', 'all'] : []} />
      )}
      {scopes.length > 1 && (
        <Segmented
          options={scopes}
          value={scope}
          onChange={setScope}
          locked={full === 'premium' ? ['faculty', 'group', 'faculties'] : []}
        />
      )}
      {league === 'on' && (
        <button type="button" onClick={() => navigate('/league')} className="text-left">
          <Card className="flex items-center gap-3 py-3">
            <FeatureTile icon="landmark" tone="brand" />
            <span className="min-w-0 flex-1 text-sm">
              <b>Fakultetlar ligasi</b> — fakultetingiz bilan birga bellashing: ball, betlar, kitoblar va tadbirlar
            </span>
            <Icon name="chevron-right" size={18} className="shrink-0 text-app-hint" />
          </Card>
        </button>
      )}
      {!isFree && full !== 'on' ? (
        <FeatureLocked code="ranking_full" access={full} />
      ) : scope === 'faculties' ? (
        <FacultyBoard period={period} />
      ) : (
        <Leaderboard period={period} scope={scope} />
      )}
      <p className="px-2 text-center text-xs text-app-hint">
        Teng ballarda: davomat bali, keyin test bali, keyin ballni avvalroq to'plagan yuqorida turadi.
      </p>
    </>
  )
}
