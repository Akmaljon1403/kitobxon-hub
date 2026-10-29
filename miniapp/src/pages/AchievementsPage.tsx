import { Icon } from '../components/Icon'
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
    <Card className={`flex flex-col items-center gap-1 px-2 py-4 text-center ${unlocked ? 'ring-1 ring-gold-400/30' : 'opacity-70'}`}>
      {unlocked ? (
        <span aria-hidden className="text-4xl">
          {item.icon}
        </span>
      ) : (
        <span className="grid size-12 place-items-center rounded-full bg-app-surface text-app-hint">
          <Icon name="lock" size={24} />
        </span>
      )}
      <p className="text-sm font-semibold leading-tight">{item.title}</p>
      <p className="text-xs leading-snug text-app-hint">{item.description}</p>
      {unlocked && (
        <p className="mt-1 flex items-center justify-center gap-1 text-[11px] text-green-600 dark:text-green-300">
          <Icon name="check" size={12} />
          {formatDate(item.unlocked_at)}
        </p>
      )}
      {showProgress && (
        <div className="mt-1 w-full px-2" aria-label={`${item.progress} / ${item.threshold}`}>
          <div className="h-1.5 rounded-full bg-app-surface">
            <div
              className="h-1.5 rounded-full bg-brand-gradient"
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
          <h1 className="flex items-center gap-2.5 font-serif text-2xl font-bold">
            <Icon name="medal" size={24} className="shrink-0 text-brand-600 dark:text-brand-300" />
            Yutuqlar
          </h1>
          <p className="text-sm text-app-hint">
            {unlocked.length} / {state.data.length} ta yutuq qo'lga kiritildi
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate('/certificates')}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-app-surface px-3 py-2 text-sm font-medium"
        >
          <Icon name="graduation-cap" size={16} />
          Sertifikatlarim
        </button>
      </div>
      {state.data.length === 0 && <EmptyState icon="medal" title="Hozircha yutuqlar yo'q" />}
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
