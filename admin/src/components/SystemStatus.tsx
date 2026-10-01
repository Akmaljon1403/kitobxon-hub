import { Badge, Button, Card } from './ui'
import { LoadingState } from './StateViews'
import { useAsync } from '../hooks/useAsync'
import { useSession } from '../store/session'
import { navigate } from '../utils/router'

type CheckStatus = 'ok' | 'info' | 'warning' | 'error'

interface SystemStatusResponse {
  summary: 'ok' | 'warning' | 'error'
  checked_at: string
  checks: { key: string; status: CheckStatus; title: string; detail: string }[]
}

// Status is shown with an icon and a word, never by colour alone.
const LOOK: Record<CheckStatus, { icon: string; label: string; tone: 'success' | 'info' | 'warning' | 'danger' }> = {
  ok: { icon: '✅', label: 'Joyida', tone: 'success' },
  info: { icon: 'ℹ️', label: "Ma'lumot", tone: 'info' },
  warning: { icon: '⚠️', label: "E'tibor bering", tone: 'warning' },
  error: { icon: '❌', label: 'Xato', tone: 'danger' },
}

function useSystemStatus() {
  const { api } = useSession()
  return useAsync((signal) => api<SystemStatusResponse>('/api/v1/admin/system/status', { signal }))
}

/** Full list of readiness checks (Settings page). */
export function SystemStatusCard() {
  const { state, reload } = useSystemStatus()
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">🩺 Tizim holati</h2>
          <p className="text-xs text-app-hint">Server, bot, ma'lumotlar bazasi va fayllar ombori to'g'ri ishlayotganini tekshiradi</p>
        </div>
        <Button variant="secondary" onClick={reload} loading={state.status === 'loading'}>
          Qayta tekshirish
        </Button>
      </div>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <p className="text-sm text-app-danger">{state.error.message}</p>}
      {state.status === 'success' && (
        <ul className="divide-y divide-app-border rounded-lg border border-app-border">
          {state.data.checks.map((check) => (
            <li key={check.key} className="grid gap-1 px-3 py-2.5 sm:grid-cols-[12rem_1fr_auto] sm:items-center sm:gap-3">
              <span className="text-sm font-medium">
                <span aria-hidden="true">{LOOK[check.status].icon} </span>
                {check.title}
              </span>
              <span className="text-sm text-app-hint">{check.detail}</span>
              <span>
                <Badge tone={LOOK[check.status].tone}>{LOOK[check.status].label}</Badge>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/** Dashboard banner: appears only when something needs the owner's attention. */
export function SystemStatusBanner() {
  const { state } = useSystemStatus()
  if (state.status !== 'success' || state.data.summary === 'ok') return null
  const problems = state.data.checks.filter((check) => check.status === 'warning' || check.status === 'error')
  const serious = state.data.summary === 'error'
  return (
    <Card className={`flex flex-wrap items-center justify-between gap-3 p-4 ${serious ? 'border-app-danger' : ''}`}>
      <div>
        <p className="font-semibold">
          <span aria-hidden="true">{serious ? '❌' : '⚠️'} </span>
          Tizimda {problems.length} ta e'tibor talab qiladigan holat bor
        </p>
        <p className="text-sm text-app-hint">{problems.map((check) => check.title).join(' · ')}</p>
      </div>
      <Button variant="secondary" onClick={() => navigate('/settings')}>
        Batafsil →
      </Button>
    </Card>
  )
}
