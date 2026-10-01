import { ErrorState, LoadingState } from '../components/StateViews'
import { Card, PageHeader } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useSession } from '../store/session'
import type { Statistics } from '../types/api'
import { navigate } from '../utils/router'
import { TopMembers } from './ScoresPage'

function StatTile({ label, value, hint, onClick }: { label: string; value: number; hint?: string; onClick?: () => void }) {
  const content = (
    <>
      <p className="text-sm text-app-hint">{label}</p>
      <p className="mt-1 text-3xl font-semibold tabular-nums">{value.toLocaleString('uz-UZ')}</p>
      {hint && <p className="mt-1 text-xs text-app-hint">{hint}</p>}
    </>
  )
  return onClick ? (
    <button type="button" onClick={onClick} className="rounded-xl border border-app-border bg-app-bg p-4 text-left hover:bg-app-surface">
      {content}
    </button>
  ) : (
    <div className="rounded-xl border border-app-border bg-app-bg p-4">{content}</div>
  )
}

function FacultyBars({ rows }: { rows: Statistics['faculties'] }) {
  const max = Math.max(1, ...rows.map((row) => row.members))
  return (
    <Card className="p-4">
      <h2 className="font-semibold">Fakultetlar bo'yicha faol a'zolar</h2>
      <ul className="mt-4 flex flex-col gap-3">
        {rows.map((row) => (
          <li key={row.name} className="grid grid-cols-[minmax(0,14rem)_1fr_3rem] items-center gap-3 text-sm">
            <span className="truncate" title={row.name}>
              {row.name}
            </span>
            <div className="h-2.5 rounded-full bg-app-surface" title={`${row.name}: ${row.members} a'zo`}>
              <div className="h-2.5 rounded-full bg-app-button" style={{ width: `${(row.members / max) * 100}%` }} />
            </div>
            <span className="text-right tabular-nums text-app-hint">{row.members}</span>
          </li>
        ))}
        {rows.length === 0 && <li className="text-sm text-app-hint">Fakultetlar hali qo'shilmagan.</li>}
      </ul>
    </Card>
  )
}

export function DashboardPage() {
  const { admin, api, can } = useSession()
  const allowed = can('ANALYTICS_VIEW')
  const { state, reload } = useAsync(
    (signal) => (allowed ? api<Statistics>('/api/v1/admin/statistics', { signal }) : Promise.resolve(null)),
    [allowed],
  )

  return (
    <>
      <PageHeader title={`Assalomu alaykum, ${admin?.first_name ?? ''}!`} subtitle="Klub faoliyatining qisqacha ko'rinishi" />
      {!allowed && (
        <Card className="p-4 text-sm text-app-hint">Statistikani ko'rish uchun «ANALYTICS_VIEW» ruxsati kerak.</Card>
      )}
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Jami a'zolar" value={state.data.users.total} onClick={() => navigate('/members')} />
            <StatTile label="Faol a'zolar" value={state.data.users.active} />
            <StatTile
              label="Tasdiq kutayotganlar"
              value={state.data.users.pending}
              hint={state.data.users.pending ? "A'zolar bo'limida tasdiqlang" : undefined}
              onClick={() => navigate('/members')}
            />
            <StatTile label="So'nggi 7 kunda qo'shilgan" value={state.data.users.new_last_7_days} />
            <StatTile label="Faol kitoblar" value={state.data.books.active} onClick={() => navigate('/books')} />
            <StatTile label="Qoralama kitoblar" value={state.data.books.draft} />
            <StatTile label="Kitob o'qiyotganlar" value={state.data.books.readers} />
            <StatTile label="O'qib tugatilgan kitoblar" value={state.data.books.completions} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <FacultyBars rows={state.data.faculties} />
            {can('SCORE_VIEW') && <TopMembers limit={5} />}
          </div>
        </>
      )}
    </>
  )
}
