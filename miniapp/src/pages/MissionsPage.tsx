import { useCallback, useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Mission, MissionOptions } from '../types/api'
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

  async function act(action: 'take' | 'give-up' | 'delete') {
    if (action === 'give-up' && !(await confirmAction('Missiyani to‘xtatasizmi? Keyin qaytadan boshlash mumkin.'))) return
    if (action === 'delete' && !(await confirmAction('O‘z missiyangizni butunlay o‘chirasizmi?'))) return
    setBusy(true)
    setError(null)
    try {
      onChange(
        action === 'delete'
          ? await api<Mission[]>(`/api/v1/me/missions/${mission.id}`, { method: 'DELETE' })
          : await api<Mission[]>(`/api/v1/me/missions/${mission.id}/${action}`, { method: 'POST' }),
      )
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
        <div className="flex flex-col items-end gap-1">
          {mission.personal && <Badge tone="info">O‘zim uchun</Badge>}
          {mission.status === 'COMPLETED' && <Badge tone="success">Bajarildi</Badge>}
        </div>
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
      {mission.status === 'ACTIVE' && !mission.personal && (
        <Button variant="ghost" loading={busy} onClick={() => void act('give-up')}>
          To‘xtatish
        </Button>
      )}
      {mission.personal && (
        <Button variant="ghost" loading={busy} onClick={() => void act('delete')}>
          🗑 O‘chirish
        </Button>
      )}
    </Card>
  )
}

const PERIODS = [7, 14, 30]

/** «🎯 O‘z missiyam»: the member sets a goal for themself; it starts at once and counts the same way. */
function OwnMissionForm({ onCreated, onClose }: { onCreated: (items: Mission[]) => void; onClose: () => void }) {
  const { api } = useAuth()
  const options = useAsync((signal) => api<MissionOptions>('/api/v1/me/missions/options', { signal }))
  const [title, setTitle] = useState('')
  const [icon, setIcon] = useState('🎯')
  const [metric, setMetric] = useState('PAGES')
  const [target, setTarget] = useState('100')
  const [days, setDays] = useState(7)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (options.state.status === 'loading') return <LoadingState />
  if (options.state.status === 'error') return <ErrorState message={options.state.error.message} onRetry={options.reload} />
  const data = options.state.data
  if (!data.enabled) {
    return (
      <Card>
        <p className="text-sm text-app-hint">Shaxsiy missiya yaratish hozircha yopiq.</p>
      </Card>
    )
  }
  const chosen = data.metrics.find((item) => item.code === metric) ?? data.metrics[0]
  const number = Number(target)
  const earns = data.points > 0 && number >= chosen.points_from

  async function create() {
    setBusy(true)
    setError(null)
    try {
      onCreated(
        await api<Mission[]>('/api/v1/me/missions', {
          method: 'POST',
          body: { title: title.trim(), icon, metric, target: number, period_days: days },
        }),
      )
      haptic('success')
      onClose()
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-3 ring-1 ring-app-button/40">
      <p className="font-semibold">🎯 O‘z missiyamni yaratish</p>
      <input
        placeholder="Nomi: masalan, «Imtihondan oldin 3 ta kitob»"
        value={title}
        maxLength={80}
        onChange={(event) => setTitle(event.target.value)}
        className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
      />
      <div className="flex flex-wrap gap-1.5">
        {data.icons.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setIcon(item)}
            className={`size-10 rounded-xl text-xl ${icon === item ? 'bg-app-button/20 ring-2 ring-app-button' : 'bg-app-surface'}`}
          >
            {item}
          </button>
        ))}
      </div>
      <label className="flex flex-col gap-1 text-sm">
        Nimani hisoblaymiz?
        <select
          value={metric}
          onChange={(event) => {
            const next = data.metrics.find((item) => item.code === event.target.value)
            setMetric(event.target.value)
            if (next) setTarget(String(Math.max(next.min, next.points_from)))
          }}
          className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
        >
          {data.metrics.map((item) => (
            <option key={item.code} value={item.code}>
              {item.title}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Maqsad ({chosen.unit}, {chosen.min}–{chosen.max})
        <input
          type="number"
          inputMode="numeric"
          min={chosen.min}
          max={chosen.max}
          value={target}
          onChange={(event) => setTarget(event.target.value)}
          className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
        />
      </label>
      <div className="flex flex-col gap-1 text-sm">
        Muddat
        <div className="flex gap-1.5">
          {PERIODS.map((period) => (
            <button
              key={period}
              type="button"
              onClick={() => setDays(period)}
              className={`flex-1 rounded-full px-3 py-1.5 ${days === period ? 'bg-app-button text-app-button-text' : 'bg-app-surface text-app-hint'}`}
            >
              {period} kun
            </button>
          ))}
        </div>
      </div>
      <p className="rounded-xl bg-app-surface px-3 py-2 text-sm">
        {icon} <b>{title.trim() || 'Missiyam'}</b>: {days} kun ichida {number || '…'} {chosen.unit}.{' '}
        {earns
          ? `Bajarsangiz — 🎁 +${data.points} ball.`
          : data.points > 0
            ? `Ball ${chosen.points_from} ${chosen.unit}dan boshlab beriladi — lekin o‘zingiz uchun har qanday maqsad yaxshi!`
            : 'Natija kundalik, javon, tadbir va testlardan o‘zi hisoblanadi.'}
      </p>
      {error && <p className="text-sm text-app-danger">{error}</p>}
      <Button loading={busy} disabled={title.trim().length < 3 || !number} onClick={() => void create()}>
        🚀 Yaratish va boshlash
      </Button>
      <Button variant="ghost" onClick={onClose}>
        Bekor qilish
      </Button>
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
  const [creating, setCreating] = useState(false)

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
          Klub missiyasini boshlang yoki o‘zingizga maqsad qo‘ying — natija kundalik, javon, tadbir va testlardagi haqiqiy
          faolligingizdan o‘zi hisoblanadi.
        </p>
      </div>
      {creating ? (
        <OwnMissionForm onCreated={setItems} onClose={() => setCreating(false)} />
      ) : (
        <Button variant="secondary" onClick={() => setCreating(true)}>
          ➕ O‘z missiyamni yaratish
        </Button>
      )}
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
