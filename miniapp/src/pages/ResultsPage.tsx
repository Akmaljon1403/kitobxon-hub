import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Card, PageTitle, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useFeature } from '../components/FeatureGate'
import { useAuth } from '../store/auth'
import { useHomeBackButton } from '../hooks/useBackButton'
import { navigate } from '../utils/router'
import type { MyRanking, MyScores, ScoreEntry } from '../types/api'
import { formatDate } from '../utils/format'

const GROUPS: { label: string; icon: string; categories: string[] }[] = [
  { label: 'Davomat', icon: '📅', categories: ['ATTENDANCE'] },
  { label: 'Testlar', icon: '📝', categories: ['TEST', 'TEST_RANK_BONUS'] },
  { label: 'Kitoblar', icon: '📚', categories: ['BOOK_COMPLETION', 'CAMPAIGN'] },
  { label: 'Bonuslar', icon: '🎁', categories: ['ACHIEVEMENT', 'MANUAL'] },
]

const CATEGORY_LABELS: Record<string, string> = {
  ATTENDANCE: 'Tadbirda qatnashish',
  TEST: 'Test',
  TEST_RANK_BONUS: "Testda sovrinli o'rin",
  BOOK_COMPLETION: "Kitobni o'qib tugatish",
  CAMPAIGN: 'Kitobxonlik kampaniyasi',
  ACHIEVEMENT: 'Yutuq',
  MANUAL: 'Tuzatish',
  REVERSAL: 'Bekor qilindi',
}

function HistoryItem({ entry }: { entry: ScoreEntry }) {
  const positive = entry.amount > 0
  return (
    <li className="flex items-start justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <p className={`text-[15px] ${entry.is_reversed ? 'text-app-hint line-through' : ''}`}>
          {CATEGORY_LABELS[entry.category] ?? entry.category}
          {entry.category === 'REVERSAL' && ` (${CATEGORY_LABELS[entry.effective_category] ?? ''})`}
        </p>
        <p className="truncate text-xs text-app-hint">
          {[entry.source_title, entry.reason, formatDate(entry.created_at)].filter(Boolean).join(' · ')}
        </p>
      </div>
      <span className={`shrink-0 font-semibold tabular-nums ${positive ? 'text-green-600 dark:text-green-300' : 'text-app-danger'}`}>
        {positive ? '+' : ''}
        {entry.amount}
      </span>
    </li>
  )
}

export function ResultsPage() {
  useHomeBackButton()
  const statsAccess = useFeature('personal_stats')
  const { api } = useAuth()
  const scores = useAsync((signal) => api<MyScores>('/api/v1/me/scores?limit=100', { signal }))
  const ranks = useAsync((signal) => api<MyRanking>('/api/v1/me/ranking', { signal }))

  if (scores.state.status === 'loading') return <LoadingState />
  if (scores.state.status === 'error') return <ErrorState message={scores.state.error.message} onRetry={scores.reload} />
  const data = scores.state.data
  const sum = (categories: string[]) => categories.reduce((total, key) => total + (data.breakdown[key] ?? 0), 0)

  return (
    <>
      <PageTitle icon="bar-chart">Natijalarim</PageTitle>
      <Card className="flex flex-col items-center gap-1 border-0 bg-brand-gradient py-6 text-center text-white shadow-[var(--shadow-brand)] ring-1 ring-white/10">
        <p className="text-sm text-white/75">Jami ball</p>
        <p className="font-serif text-4xl font-bold tabular-nums text-gold-300">{data.total}</p>
        {data.season && (
          <p className="text-xs text-white/70">
            {data.season.name}: {data.season.total} ball
          </p>
        )}
      </Card>

      {statsAccess !== 'off' && (
        <button type="button" onClick={() => navigate('/stats')}>
          <Card className="flex items-center justify-between gap-2 py-3 text-left">
            <span className="text-[15px] font-medium">
              📈 Batafsil statistika{statsAccess === 'premium' && <span className="text-app-hint"> · 💎 Premium</span>}
            </span>
            <span className="text-app-link">→</span>
          </Card>
        </button>
      )}

      <div className="grid grid-cols-2 gap-2">
        {GROUPS.map((group) => (
          <Card key={group.label} className="flex flex-col gap-0.5">
            <span className="text-sm text-app-hint">
              {group.icon} {group.label}
            </span>
            <span className="font-serif text-2xl font-bold tabular-nums">{sum(group.categories)}</span>
          </Card>
        ))}
      </div>

      {ranks.state.status === 'success' && (
        <Card className="grid grid-cols-3 text-center">
          {(
            [
              ['Hafta', ranks.state.data.week],
              ['Oy', ranks.state.data.month],
              ['Umumiy', ranks.state.data.all],
            ] as const
          ).map(([label, row]) => (
            <div key={label}>
              <p className="text-xs text-app-hint">{label}</p>
              <p className="text-lg font-semibold">{row ? `${row.rank}-o'rin` : '—'}</p>
            </div>
          ))}
        </Card>
      )}

      <SectionTitle>Ballar tarixi</SectionTitle>
      {data.history.length === 0 ? (
        <EmptyState icon="bar-chart" title="Hali ball yo'q">
          Tadbirlarda qatnashing, testlarni ishlang va kitoblarni o'qing.
        </EmptyState>
      ) : (
        <Card className="divide-y divide-app-hint/10 py-1">
          <ul className="divide-y divide-app-hint/10">
            {data.history.map((entry) => (
              <HistoryItem key={entry.id} entry={entry} />
            ))}
          </ul>
        </Card>
      )}
    </>
  )
}
