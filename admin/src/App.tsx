import { ErrorState, LoadingState } from './components/StateViews'
import { useAsync } from './hooks/useAsync'
import { apiRequest } from './services/api'

interface HealthStatus {
  status: string
  service: string
}

const CHECKS: { path: string; label: string }[] = [
  { path: '/health', label: 'API' },
  { path: '/health/db', label: "Ma'lumotlar bazasi" },
  { path: '/health/redis', label: 'Redis (ixtiyoriy)' },
]

// Phase 1 shell: shows system health. Login, navigation and management pages follow in later phases.
export default function App() {
  const { state, reload } = useAsync(async (signal) =>
    Promise.all(
      CHECKS.map(async (check) => {
        try {
          const result = await apiRequest<HealthStatus>(check.path, { signal })
          return { ...check, ok: true, detail: result.status }
        } catch (error) {
          return { ...check, ok: false, detail: error instanceof Error ? error.message : 'xatolik' }
        }
      }),
    ),
  )

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Kitobxon Hub — Admin panel</h1>
        <p className="text-sm text-app-hint">Tizim holati</p>
      </header>
      <section className="rounded-2xl border border-app-border bg-app-bg p-6">
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <ul className="divide-y divide-app-border">
            {state.data.map((item) => (
              <li key={item.path} className="flex items-center justify-between py-3 text-sm">
                <span>{item.label}</span>
                <span className={item.ok ? 'text-green-600' : 'text-app-danger'}>
                  {item.ok ? `✅ ${item.detail}` : `❌ ${item.detail}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
