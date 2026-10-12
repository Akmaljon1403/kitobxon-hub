import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'

type Status = 'DRAFT' | 'ACTIVE' | 'ARCHIVED'

interface AdminMission {
  id: string
  title: string
  description: string | null
  icon: string
  metric: string
  metric_title: string
  unit: string
  target: number
  period_days: number
  reward_points: number
  status: Status
  taken: number
  completed: number
  running: number
  completion_rate: number | null
}

interface Metric {
  code: string
  title: string
  unit: string
}

interface Draft {
  title: string
  description: string
  icon: string
  metric: string
  target: number
  period_days: number
  reward_points: number
  status: Status
}

const STATUS: Record<Status, { label: string; tone: 'success' | 'neutral' | 'warning' }> = {
  ACTIVE: { label: 'Faol', tone: 'success' },
  DRAFT: { label: 'Qoralama', tone: 'warning' },
  ARCHIVED: { label: 'Arxiv', tone: 'neutral' },
}

const EMPTY: Draft = { title: '', description: '', icon: '🎯', metric: 'PAGES', target: 100, period_days: 7, reward_points: 10, status: 'ACTIVE' }

/** «🎯 Missiyalar»: personal goals members take in the Mini App; progress is counted from real activity. */
interface PersonalMission {
  id: string
  title: string
  description: string | null
  icon: string
  unit: string
  target: number
  period_days: number
  status: 'ACTIVE' | 'COMPLETED' | 'EXPIRED' | null
  progress: number
  deadline: string | null
  completed_at: string | null
  owner_name: string
  group_name: string | null
  created_at: string
}

interface PersonalOverview {
  created: number
  members: number
  running: number
  completed: number
  popular: { metric: string; title: string; count: number }[]
  items: PersonalMission[]
}

const PERSONAL_STATUS: Record<string, { label: string; tone: 'success' | 'info' | 'neutral' }> = {
  ACTIVE: { label: 'Davom etmoqda', tone: 'info' },
  COMPLETED: { label: 'Bajarildi', tone: 'success' },
  EXPIRED: { label: 'Muddati o‘tdi', tone: 'neutral' },
}

/** What members set for themselves: the admins see it, take good ideas for everybody, remove unsuitable ones. */
function PersonalMissions({ onPromoted }: { onPromoted: () => void }) {
  const { api } = useSession()
  const overview = useAsync((signal) => api<PersonalOverview>('/api/v1/admin/missions/personal', { signal }))
  const [message, setMessage] = useState<string | null>(null)

  async function promote(mission: PersonalMission) {
    await api(`/api/v1/admin/missions/personal/${mission.id}/promote`, { method: 'POST' })
    setMessage(`«${mission.title}» klub missiyalariga qoralama bo‘lib qo‘shildi — tahrirlab, «Faol» qiling.`)
    onPromoted()
  }

  async function remove(mission: PersonalMission) {
    if (!window.confirm(`«${mission.title}» missiyasini o‘chirasizmi? A’zoning o‘zi ham uni boshqa ko‘rmaydi.`)) return
    await api(`/api/v1/admin/missions/personal/${mission.id}`, { method: 'DELETE' })
    overview.reload()
  }

  if (overview.state.status === 'loading') return <LoadingState />
  if (overview.state.status === 'error') return <ErrorState message={overview.state.error.message} onRetry={overview.reload} />
  const data = overview.state.data
  return (
    <Card className="flex flex-col gap-3 p-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-4 pt-4">
        <h2 className="font-semibold">🙋 A’zolarning o‘z missiyalari</h2>
        <p className="text-sm text-app-hint">
          {data.created} ta missiya · {data.members} a’zo · hozir {data.running} · bajarilgan {data.completed}
        </p>
      </div>
      {data.popular.length > 0 && (
        <p className="px-4 text-sm text-app-hint">
          Eng ko‘p tanlanadigani: {data.popular.slice(0, 3).map((item) => `${item.title} (${item.count})`).join(', ')}
        </p>
      )}
      {message && <p className="mx-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">{message}</p>}
      <Table head={['Missiya', 'A’zo', 'Holat', '']}>
        {data.items.length === 0 && <EmptyRow colSpan={4} text="A’zolar hali o‘zlariga missiya yaratmagan" />}
        {data.items.map((mission) => (
          <tr key={mission.id}>
            <td className="px-4 py-3">
              <p className="font-medium">
                {mission.icon} {mission.title}
              </p>
              <p className="text-xs text-app-hint">
                {mission.period_days} kunda {mission.target} {mission.unit}
              </p>
            </td>
            <td className="px-4 py-3 text-sm">
              {mission.owner_name}
              {mission.group_name && <p className="text-xs text-app-hint">{mission.group_name}-guruh</p>}
            </td>
            <td className="px-4 py-3 text-sm">
              {mission.status && <Badge tone={PERSONAL_STATUS[mission.status].tone}>{PERSONAL_STATUS[mission.status].label}</Badge>}
              <p className="text-xs tabular-nums text-app-hint">
                {mission.progress}/{mission.target}
              </p>
            </td>
            <td className="whitespace-nowrap px-4 py-3 text-right">
              <Button variant="ghost" onClick={() => void promote(mission)}>
                ⬆️ Hammaga
              </Button>
              <Button variant="ghost" onClick={() => void remove(mission)}>
                🗑
              </Button>
            </td>
          </tr>
        ))}
      </Table>
    </Card>
  )
}

export function MissionsPage() {
  const { api } = useSession()
  const list = useAsync((signal) => api<AdminMission[]>('/api/v1/admin/missions', { signal }))
  const metrics = useAsync((signal) => api<Metric[]>('/api/v1/admin/missions/metrics', { signal }))
  const [editing, setEditing] = useState<{ id: string | null; draft: Draft } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    if (!editing) return
    setBusy(true)
    setError(null)
    try {
      const body = { ...editing.draft, description: editing.draft.description.trim() || null }
      if (editing.id) await api(`/api/v1/admin/missions/${editing.id}`, { method: 'PUT', body })
      else await api('/api/v1/admin/missions', { method: 'POST', body })
      setEditing(null)
      list.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Saqlab bo‘lmadi.')
    } finally {
      setBusy(false)
    }
  }

  function edit(mission: AdminMission) {
    setError(null)
    setEditing({
      id: mission.id,
      draft: {
        title: mission.title,
        description: mission.description ?? '',
        icon: mission.icon,
        metric: mission.metric,
        target: mission.target,
        period_days: mission.period_days,
        reward_points: mission.reward_points,
        status: mission.status,
      },
    })
  }

  const unit = metrics.state.status === 'success' ? metrics.state.data.find((m) => m.code === editing?.draft.metric)?.unit : ''

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="🎯 Missiyalar"
        subtitle="A’zolar ilovada missiyani boshlaydi; natija kundalik, javon, davomat va testlardan o‘zi hisoblanadi. Bajarganga ball."
        actions={
          <Button
            onClick={() => {
              setError(null)
              setEditing({ id: null, draft: EMPTY })
            }}
          >
            ➕ Yangi missiya
          </Button>
        }
      />
      {list.state.status === 'loading' && <LoadingState />}
      {list.state.status === 'error' && <ErrorState message={list.state.error.message} onRetry={list.reload} />}
      {list.state.status === 'success' && (
        <Card className="p-0">
          <Table head={['Missiya', 'Shart', 'Ball', 'Holat', 'Oldi / bajardi', '']}>
            {list.state.data.length === 0 && <EmptyRow colSpan={6} text="Hali missiya yo‘q" />}
            {list.state.data.map((mission) => (
              <tr key={mission.id}>
                <td className="px-4 py-3">
                  <p className="font-medium">
                    {mission.icon} {mission.title}
                  </p>
                  {mission.description && <p className="text-xs text-app-hint">{mission.description}</p>}
                </td>
                <td className="px-4 py-3 text-sm">
                  {mission.period_days} kunda {mission.target} {mission.unit}
                  <p className="text-xs text-app-hint">{mission.metric_title}</p>
                </td>
                <td className="px-4 py-3 tabular-nums">+{mission.reward_points}</td>
                <td className="px-4 py-3">
                  <Badge tone={STATUS[mission.status].tone}>{STATUS[mission.status].label}</Badge>
                </td>
                <td className="px-4 py-3 text-sm tabular-nums">
                  {mission.taken} / {mission.completed}
                  {mission.completion_rate !== null && <span className="text-app-hint"> ({mission.completion_rate}%)</span>}
                  {mission.running > 0 && <p className="text-xs text-app-hint">hozir: {mission.running}</p>}
                </td>
                <td className="px-4 py-3 text-right">
                  <Button variant="ghost" onClick={() => edit(mission)}>
                    Tahrirlash
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}

      <PersonalMissions onPromoted={list.reload} />

      {editing && (
        <Modal
          title={editing.id ? 'Missiyani tahrirlash' : 'Yangi missiya'}
          onClose={() => setEditing(null)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setEditing(null)}>
                Bekor
              </Button>
              <Button loading={busy} disabled={editing.draft.title.trim().length < 3} onClick={() => void save()}>
                Saqlash
              </Button>
            </>
          }
        >
          <div className="grid grid-cols-[5rem_1fr] gap-3">
            <Field label="Belgi">
              <Input value={editing.draft.icon} maxLength={16} onChange={(e) => setEditing({ ...editing, draft: { ...editing.draft, icon: e.target.value } })} />
            </Field>
            <Field label="Nomi">
              <Input
                value={editing.draft.title}
                maxLength={160}
                placeholder="7 kunda 100 bet"
                onChange={(e) => setEditing({ ...editing, draft: { ...editing.draft, title: e.target.value } })}
              />
            </Field>
          </div>
          <Field label="Tavsif (ixtiyoriy)">
            <Textarea
              rows={2}
              value={editing.draft.description}
              maxLength={1000}
              onChange={(e) => setEditing({ ...editing, draft: { ...editing.draft, description: e.target.value } })}
            />
          </Field>
          <Field label="Nima hisoblanadi" hint={editing.id ? 'A’zolar olgan missiyada shart va maqsadni o‘zgartirib bo‘lmaydi' : undefined}>
            <Select value={editing.draft.metric} onChange={(e) => setEditing({ ...editing, draft: { ...editing.draft, metric: e.target.value } })}>
              {metrics.state.status === 'success' &&
                metrics.state.data.map((metric) => (
                  <option key={metric.code} value={metric.code}>
                    {metric.title}
                  </option>
                ))}
            </Select>
          </Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label={`Maqsad (${unit ?? ''})`}>
              <Input
                type="number"
                min={1}
                value={editing.draft.target}
                onChange={(e) => setEditing({ ...editing, draft: { ...editing.draft, target: Number(e.target.value) } })}
              />
            </Field>
            <Field label="Muddat (kun)">
              <Input
                type="number"
                min={1}
                max={366}
                value={editing.draft.period_days}
                onChange={(e) => setEditing({ ...editing, draft: { ...editing.draft, period_days: Number(e.target.value) } })}
              />
            </Field>
            <Field label="Ball">
              <Input
                type="number"
                min={0}
                max={1000}
                value={editing.draft.reward_points}
                onChange={(e) => setEditing({ ...editing, draft: { ...editing.draft, reward_points: Number(e.target.value) } })}
              />
            </Field>
          </div>
          <Field label="Holat">
            <Select value={editing.draft.status} onChange={(e) => setEditing({ ...editing, draft: { ...editing.draft, status: e.target.value as Status } })}>
              <option value="ACTIVE">Faol — a’zolar ko‘radi</option>
              <option value="DRAFT">Qoralama — yashirin</option>
              <option value="ARCHIVED">Arxiv — yangi a’zolar ololmaydi</option>
            </Select>
          </Field>
          <InlineError message={error} />
        </Modal>
      )}
    </div>
  )
}
