import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Card } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { ClubTest } from '../types/api'
import { formatEventDate } from '../utils/format'
import { useHomeBackButton } from '../hooks/useBackButton'
import { navigate } from '../utils/router'

export function TestStateBadge({ test }: { test: ClubTest }) {
  if (test.in_progress) return <Badge tone="warning">⏳ Davom etmoqda</Badge>
  if (test.state === 'OPEN') return <Badge tone="success">Ochiq</Badge>
  if (test.state === 'UPCOMING') return <Badge tone="info">Tez kunda</Badge>
  return <Badge>Yopilgan</Badge>
}

function TestCard({ test }: { test: ClubTest }) {
  const finished = test.attempts.filter((attempt) => attempt.status !== 'IN_PROGRESS')
  const permanent = test.kind === 'PERMANENT'
  const perfect = permanent && (test.best_score ?? 0) >= test.max_score
  return (
    <button type="button" className="text-left" onClick={() => navigate(`/tests/${test.id}`)}>
      <Card className="flex flex-col gap-1.5">
        <p className="text-xs font-medium text-app-link">
          {permanent
            ? '♾ Doim ochiq — cheksiz urinish'
            : test.state === 'UPCOMING'
              ? `Boshlanadi: ${formatEventDate(test.starts_at)}`
              : `Yopiladi: ${formatEventDate(test.ends_at)}`}
        </p>
        <h2 className="font-semibold">{test.title}</h2>
        {test.book_title && <p className="text-sm text-app-hint">📚 {test.book_title}</p>}
        <p className="text-sm text-app-hint">
          ❓ {test.question_count} savol · ⏱ {test.duration_minutes} daqiqa
          {permanent ? ' · 🏆 100% uchun bonus' : ` · 🏆 ${test.max_score} ballgacha`}
        </p>
        <div className="flex items-center justify-between gap-2 pt-1">
          <TestStateBadge test={test} />
          {permanent
            ? perfect && <span className="text-sm font-semibold text-green-600 dark:text-green-300">✅ 100% — bonus olingan</span>
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

function Section({ title, hint, tests }: { title: string; hint: string; tests: ClubTest[] }) {
  if (tests.length === 0) return null
  return (
    <section className="flex flex-col gap-2">
      <div className="px-1">
        <h2 className="text-base font-semibold">{title}</h2>
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
      <h1 className="px-1 pt-1 font-serif text-2xl font-bold">📝 Testlar</h1>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.length === 0 && (
        <EmptyState icon="📝" title="Hozircha testlar yo'q">
          Test e'lon qilinganda shu yerda ko'rinadi va bot orqali xabar olasiz.
        </EmptyState>
      )}
      {state.status === 'success' && state.data.length > 0 && (
        <div className="flex flex-col gap-5">
          <Section
            title="📅 Tadbir testlari"
            hint="Muddatli testlar — ball to'plang, yopilgach eng yaxshilar bonus oladi."
            tests={state.data.filter((test) => test.kind !== 'PERMANENT')}
          />
          <Section
            title="♾ Doimiy testlar"
            hint="Istalgan vaqtda, cheksiz yechish mumkin. Birinchi marta 100% yechsangiz bonus ball."
            tests={state.data.filter((test) => test.kind === 'PERMANENT')}
          />
        </div>
      )}
    </>
  )
}
