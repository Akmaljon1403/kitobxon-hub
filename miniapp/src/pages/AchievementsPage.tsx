import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { MemberAchievement } from '../types/api'
import { formatDate } from '../utils/format'
import { useHomeBackButton } from '../hooks/useBackButton'
import { navigate } from '../utils/router'

function Badge({ item }: { item: MemberAchievement }) {
  const unlocked = Boolean(item.unlocked_at)
  const showProgress = !unlocked && item.progress !== null && item.threshold > 1
  return (
    <Card className={`flex flex-col items-center gap-1 px-2 py-4 text-center ${unlocked ? '' : 'opacity-70'}`}>
      <span aria-hidden className={`text-4xl ${unlocked ? '' : 'grayscale'}`}>
        {unlocked ? item.icon : '🔒'}
      </span>
      <p className="text-sm font-semibold leading-tight">{item.title}</p>
      <p className="text-xs leading-snug text-app-hint">{item.description}</p>
      {unlocked && <p className="mt-1 text-[11px] text-green-600 dark:text-green-300">✓ {formatDate(item.unlocked_at)}</p>}
      {showProgress && (
        <div className="mt-1 w-full px-2" aria-label={`${item.progress} / ${item.threshold}`}>
          <div className="h-1.5 rounded-full bg-app-surface">
            <div
              className="h-1.5 rounded-full bg-app-button"
              style={{ width: `${Math.min(100, ((item.progress ?? 0) / item.threshold) * 100)}%` }}
            />
          </div>
          <p className="mt-1 text-[11px] tabular-nums text-app-hint">
            {item.progress} / {item.threshold}
          </p>
        </div>
      )}
      {item.points > 0 && <p className="text-[11px] text-app-hint">+{item.points} ball</p>}
    </Card>
  )
}

export function AchievementsPage() {
  useHomeBackButton()
  const { api } = useAuth()
  const { state, reload } = useAsync((signal) => api<MemberAchievement[]>('/api/v1/me/achievements', { signal }))
  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const unlocked = state.data.filter((item) => item.unlocked_at)
  const locked = state.data.filter((item) => !item.unlocked_at)
  return (
    <>
      <div className="flex items-start justify-between gap-2 px-1 pt-1">
        <div>
          <h1 className="font-serif text-2xl font-bold">🏅 Yutuqlar</h1>
          <p className="text-sm text-app-hint">
            {unlocked.length} / {state.data.length} ta yutuq qo'lga kiritildi
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate('/certificates')}
          className="shrink-0 rounded-xl bg-app-surface px-3 py-2 text-sm font-medium"
        >
          🎓 Sertifikatlarim
        </button>
      </div>
      {state.data.length === 0 && <EmptyState icon="🏅" title="Hozircha yutuqlar yo'q" />}
      {unlocked.length > 0 && (
        <>
          <SectionTitle>Qo'lga kiritilgan</SectionTitle>
          <div className="grid grid-cols-2 gap-2">
            {unlocked.map((item) => (
              <Badge key={item.code} item={item} />
            ))}
          </div>
        </>
      )}
      {locked.length > 0 && (
        <>
          <SectionTitle>Oldinda</SectionTitle>
          <div className="grid grid-cols-2 gap-2">
            {locked.map((item) => (
              <Badge key={item.code} item={item} />
            ))}
          </div>
        </>
      )}
    </>
  )
}
