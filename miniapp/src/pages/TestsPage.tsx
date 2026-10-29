import { Icon, type IconName } from '../components/Icon'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Card, PageTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { ClubTest } from '../types/api'
import { formatEventDate } from '../utils/format'
import { useHomeBackButton } from '../hooks/useBackButton'
import { navigate } from '../utils/router'

export function TestStateBadge({ test }: { test: ClubTest }) {
  if (test.in_progress) return <Badge tone="warning"><Icon name="hourglass" size={13} />Davom etmoqda</Badge>
  if (test.state === 'OPEN') return <Badge tone="success">Ochiq</Badge>
  if (test.state === 'UPCOMING') return <Badge tone="info">Tez kunda</Badge>
  return <Badge>Yopilgan</Badge>
}

function TestCard({ test }: { test: ClubTest }) {
  const finished = test.attempts.filter((attempt) => attempt.status !== 'IN_PROGRESS')
  const permanent = test.kind === 'PERMANENT'
  const perfect = permanent && (test.best_score ?? 0) >= test.max_score
  return (
    <button type="button" className="w-full text-left" onClick={() => navigate(`/tests/${test.id}`)}>
      <Card interactive className="flex flex-col gap-1.5">
        <p className="text-xs font-medium text-app-link">
          {permanent
            ? 'Doim ochiq — cheksiz urinish'
            : test.state === 'UPCOMING'
              ? `Boshlanadi: ${formatEventDate(test.starts_at)}`
              : `Yopiladi: ${formatEventDate(test.ends_at)}`}
        </p>
        <h2 className="font-serif text-lg font-bold leading-snug">{test.title}</h2>
        {test.book_title && (
          <p className="flex items-center gap-1.5 text-sm text-app-hint">
            <Icon name="book" size={14} className="shrink-0" />
            {test.book_title}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-app-hint">
          <span className="flex items-center gap-1"><Icon name="help-circle" size={14} />{test.question_count} savol</span>
          <span className="flex items-center gap-1"><Icon name="clock" size={14} />{test.duration_minutes} daqiqa</span>
          <span className="flex items-center gap-1">
            <Icon name="trophy" size={14} />
            {permanent ? '100% uchun bonus' : `${test.max_score} ballgacha`}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2 pt-1">
          <TestStateBadge test={test} />
          {permanent
            ? perfect && (
                <span className="flex items-center gap-1 text-sm font-semibold text-green-600 dark:text-green-300">
                  <Icon name="check" size={14} />100% — bonus olingan
                </span>
              )
            : finished.length > 0 && (
                <span className="text-sm font-semibold tabular-nums">
                  Natija: {test.best_score ?? 0}/{test.max_score}
                </span>
              )}
        </div>
      </Card>
    </button>
  )
}

function Section({ icon, title, hint, tests }: { icon: IconName; title: string; hint: string; tests: ClubTest[] }) {
  if (tests.length === 0) return null
  return (
    <section className="flex flex-col gap-2">
      <div className="px-1">
        <h2 className="flex items-center gap-2 font-serif text-lg font-bold">
          <Icon name={icon} size={18} className="shrink-0 text-brand-600 dark:text-brand-300" />
          {title}
        </h2>
        <p className="text-xs text-app-hint">{hint}</p>
      </div>
      {tests.map((test) => (
        <TestCard key={test.id} test={test} />
      ))}
    </section>
  )
}

export function TestsPage() {
  useHomeBackButton()
  const { api } = useAuth()
  const { state, reload } = useAsync((signal) => api<ClubTest[]>('/api/v1/tests', { signal }))

  return (
    <>
      <PageTitle icon="file-text">Testlar</PageTitle>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.length === 0 && (
        <EmptyState icon="file-text" title="Hozircha testlar yo'q">
          Test e'lon qilinganda shu yerda ko'rinadi va bot orqali xabar olasiz.
        </EmptyState>
      )}
      {state.status === 'success' && state.data.length > 0 && (
        <div className="flex flex-col gap-5">
          <Section
            icon="calendar"
            title="Tadbir testlari"
            hint="Muddatli testlar — ball to'plang, yopilgach eng yaxshilar bonus oladi."
            tests={state.data.filter((test) => test.kind !== 'PERMANENT')}
          />
          <Section
            icon="infinity"
            title="Doimiy testlar"
            hint="Istalgan vaqtda, cheksiz yechish mumkin. Birinchi marta 100% yechsangiz bonus ball."
            tests={state.data.filter((test) => test.kind === 'PERMANENT')}
          />
        </div>
      )}
    </>
  )
}
