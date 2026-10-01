import { ErrorState, LoadingState } from './components/StateViews'
import { useAsync } from './hooks/useAsync'
import { apiRequest } from './services/api'
import { getWebApp } from './utils/telegram'

interface PublicMeta {
  app_name: string
  version: string
  bot_username: string | null
}

// Phase 1 shell: proves the Mini App can reach the backend. Navigation, authentication
// and the real screens are added in the following phases.
export default function App() {
  const { state, reload } = useAsync((signal) => apiRequest<PublicMeta>('/api/v1/meta', { signal }))
  const insideTelegram = getWebApp() !== null

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col gap-4 p-4">
      <header className="rounded-2xl bg-app-bg p-5 shadow-sm">
        <h1 className="text-xl font-semibold">📚 Kitobxon Hub</h1>
        <p className="mt-1 text-sm text-app-hint">Kitobxonlar klubining raqamli platformasi</p>
      </header>

      <section className="rounded-2xl bg-app-bg p-5 shadow-sm">
        {state.status === 'loading' && <LoadingState label="Server bilan aloqa tekshirilmoqda…" />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <div className="space-y-1 text-sm">
            <p>✅ Server bilan aloqa bor.</p>
            <p className="text-app-hint">Versiya: {state.data.version}</p>
            {!insideTelegram && (
              <p className="text-app-hint">Ilovani to'liq ishlatish uchun uni Telegram bot orqali oching.</p>
            )}
          </div>
        )}
      </section>
    </main>
  )
}
