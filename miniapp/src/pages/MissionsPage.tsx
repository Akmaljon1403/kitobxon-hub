import { useCallback, useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Mission } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate } from '../utils/router'
import { confirmAction, haptic } from '../utils/telegram'
import { ProgressBar } from './ShelfPage'

function timeLeft(deadline: string | null): string {
  if (!deadline) return ''
  const left = new Date(deadline).getTime() - Date.now()
  if (left <= 0) return 'vaqt tugadi'
  const days = Math.floor(left / 86_400_000)
  const hours = Math.floor((left % 86_400_000) / 3_600_000)
  return days ? `${days} kun ${hours} soat qoldi` : `${hours} soat qoldi`
}

function MissionCard({ mission, onChange }: { mission: Mission; onChange: (items: Mission[]) => void }) {
  const { api } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function act(action: 'take' | 'give-up') {
    if (action === 'give-up' && !(await confirmAction('Missiyani to‘xtatasizmi? Keyin qaytadan boshlash mumkin.'))) return
    setBusy(true)
    setError(null)
    try {
      onChange(await api<Mission[]>(`/api/v1/me/missions/${mission.id}/${action}`, { method: 'POST' }))
      haptic('success')
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi')
    } finally {
      setBusy(false)
    }
  }

  const percent = Math.round((mission.progress / mission.target) * 100)
  return (
    <Card className={`flex flex-col gap-2 ${mission.status === 'ACTIVE' ? 'ring-1 ring-app-button/50' : ''}`}>
      <div className="flex items-start gap-3">
        <span aria-hidden className="text-3xl">
          {mission.icon}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{mission.title}</p>
          {mission.description && <p className="text-sm text-app-hint">{mission.description}</p>}
          <p className="mt-1 text-xs text-app-hint">
            {mission.period_days} kun ichida · {mission.target} {mission.unit}
            {mission.reward_points ? ` · 🎁 +${mission.reward_points} ball` : ''}
          </p>
        </div>
        {mission.status === 'COMPLETED' && <Badge tone="success">Bajarildi</Badge>}
      </div>
      {mission.status === 'ACTIVE' && (
        <>
          <ProgressBar percent={percent} />
          <p className="text-sm">
            <b>
              {mission.progress}/{mission.target}
            </b>{' '}
            {mission.unit} · <span className="text-app-hint">{timeLeft(mission.deadline)}</span>
          </p>
        </>
      )}
      {mission.status === 'COMPLETED' && mission.completed_at && (
        <p className="text-sm text-app-hint">🎉 {formatDate(mission.completed_at)} kuni bajardingiz</p>
      )}
      {error && <p className="text-sm text-app-danger">{error}</p>}
      {mission.status === null && (
        <Button loading={busy} onClick={() => void act('take')}>
          🎯 Boshlash
        </Button>
      )}
      {mission.status === 'EXPIRED' && (
        <Button variant="secondary" loading={busy} onClick={() => void act('take')}>
          🔁 Qaytadan boshlash
        </Button>
      )}
      {mission.status === 'ACTIVE' && (
        <Button variant="ghost" loading={busy} onClick={() => void act('give-up')}>
          To‘xtatish
        </Button>
      )}
    </Card>
  )
}

/** «🎯 Shaxsiy missiyalar»: small goals counted from what the member really does. */
export function MissionsPage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/shelf'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<Mission[]>('/api/v1/me/missions', { signal }))
  const [items, setItems] = useState<Mission[] | null>(null)

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const missions = items ?? state.data
  const active = missions.filter((mission) => mission.status === 'ACTIVE')
  const open = missions.filter((mission) => mission.status === null || mission.status === 'EXPIRED')
  const done = missions.filter((mission) => mission.status === 'COMPLETED')

  return (
    <div className="flex flex-col gap-3">
      <div className="px-1">
        <h1 className="text-xl font-semibold">🎯 Shaxsiy missiyalar</h1>
        <p className="text-sm text-app-hint">
          Missiyani boshlang — natija kundalik, javon, tadbir va testlardagi haqiqiy faolligingizdan o‘zi hisoblanadi.
        </p>
      </div>
      {missions.length === 0 && (
        <Card>
          <EmptyState icon="🎯" title="Hozircha missiya yo‘q">
            Tez orada yangilari qo‘shiladi.
          </EmptyState>
        </Card>
      )}
      {active.length > 0 && <SectionTitle>Davom etmoqda</SectionTitle>}
      {active.map((mission) => (
        <MissionCard key={mission.id} mission={mission} onChange={setItems} />
      ))}
      {open.length > 0 && <SectionTitle>Boshlash mumkin</SectionTitle>}
      {open.map((mission) => (
        <MissionCard key={mission.id} mission={mission} onChange={setItems} />
      ))}
      {done.length > 0 && <SectionTitle>Bajarilgan</SectionTitle>}
      {done.map((mission) => (
        <MissionCard key={mission.id} mission={mission} onChange={setItems} />
      ))}
    </div>
  )
}
