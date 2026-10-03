import { useState } from 'react'

import { Avatar } from '../components/Avatar'
import { FeatureLocked } from '../components/FeatureGate'
import { PassportCard } from '../components/PassportCard'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, SectionTitle, Toggle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Faculty, Me, NotificationSettings } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate } from '../utils/router'
import { haptic } from '../utils/telegram'

const NOTIFICATION_LABELS: Record<keyof NotificationSettings, string> = {
  event_reminders: '📅 Tadbir eslatmalari',
  test_reminders: '📝 Test eslatmalari',
  reading_reminders: "📖 O'qish muddati eslatmalari",
  quote_of_day: '💬 Kun iqtibosi',
  ranking_updates: '🏆 Reyting yangiliklari',
  achievement_alerts: '🏅 Yutuqlar haqida',
}

function ProfileEditor({ me, onDone }: { me: Me; onDone: () => void }) {
  const { api, refreshMe } = useAuth()
  const faculties = useAsync((signal) => api<Faculty[]>('/api/v1/faculties', { signal }))
  const [facultyId, setFacultyId] = useState(me.faculty?.id ?? '')
  const [course, setCourse] = useState(me.course ?? 1)
  const [group, setGroup] = useState(me.group_name ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setSaving(true)
    setError(null)
    try {
      await api<Me>('/api/v1/me', {
        method: 'PATCH',
        body: { ...(facultyId ? { faculty_id: facultyId } : {}), course, group_name: group },
      })
      await refreshMe()
      haptic('success')
      onDone()
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setSaving(false)
    }
  }

  const fieldClass = 'mt-1 w-full rounded-xl bg-app-surface px-3 py-3 text-[15px] outline-none'
  return (
    <Card className="flex flex-col gap-3">
      <label className="text-sm text-app-hint">
        Fakultet
        <select className={fieldClass} value={facultyId} onChange={(e) => setFacultyId(e.target.value)}>
          {!facultyId && <option value="">Tanlang</option>}
          {faculties.state.status === 'success' &&
            faculties.state.data.map((faculty) => (
              <option key={faculty.id} value={faculty.id}>
                {faculty.name}
              </option>
            ))}
        </select>
      </label>
      <label className="text-sm text-app-hint">
        Kurs
        <select className={fieldClass} value={course} onChange={(e) => setCourse(Number(e.target.value))}>
          {Array.from({ length: me.max_course }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>
              {n}-kurs
            </option>
          ))}
        </select>
      </label>
      <label className="text-sm text-app-hint">
        Guruh
        <input
          className={fieldClass}
          value={group}
          maxLength={16}
          onChange={(e) => setGroup(e.target.value)}
          placeholder="Masalan: 301-A"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-app-danger">
          {error}
        </p>
      )}
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" onClick={onDone}>
          Bekor qilish
        </Button>
        <Button loading={saving} onClick={save} disabled={!group.trim()}>
          Saqlash
        </Button>
      </div>
    </Card>
  )
}

function NotificationsCard() {
  const { api } = useAuth()
  const { state, reload } = useAsync((signal) =>
    api<NotificationSettings>('/api/v1/me/notification-settings', { signal }),
  )
  const [local, setLocal] = useState<NotificationSettings | null>(null)
  const [busy, setBusy] = useState(false)

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const settings = local ?? state.data

  async function change(field: keyof NotificationSettings, value: boolean) {
    const previous = settings
    setLocal({ ...settings, [field]: value })
    setBusy(true)
    try {
      setLocal(await api<NotificationSettings>('/api/v1/me/notification-settings', { method: 'PUT', body: { [field]: value } }))
      haptic('success')
    } catch {
      setLocal(previous)
      haptic('error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="divide-y divide-app-hint/10 py-1">
      {(Object.keys(NOTIFICATION_LABELS) as (keyof NotificationSettings)[]).map((field) => (
        <Toggle
          key={field}
          label={NOTIFICATION_LABELS[field]}
          checked={settings[field]}
          disabled={busy}
          onChange={(value) => change(field, value)}
        />
      ))}
    </Card>
  )
}

export function ProfilePage() {
  const { me } = useAuth()
  const [editing, setEditing] = useState(false)
  if (!me) return null

  return (
    <>
      <Card className="flex flex-col items-center gap-2 text-center">
        <Avatar me={me} size="size-20" />
        <h1 className="text-xl font-semibold">
          {me.first_name} {me.last_name}
        </h1>
        {me.telegram_username && <p className="text-sm text-app-hint">@{me.telegram_username}</p>}
        {me.is_admin && <Badge tone="info">Administrator</Badge>}
      </Card>

      {me.features.premium !== 'off' && (
        <button type="button" onClick={() => navigate('/premium')}>
          <Card className="flex items-center justify-between gap-2 py-3 text-left">
            <span className="text-[15px] font-medium">
              💎 {me.is_premium ? `Premium a'zo — ${formatDate(me.premium_until)} gacha` : 'Premium obuna'}
            </span>
            <span className="text-app-link">→</span>
          </Card>
        </button>
      )}

      {me.features.passport === 'on' ? (
        <PassportCard />
      ) : (
        me.features.passport === 'premium' && <FeatureLocked code="passport" access="premium" />
      )}

      <SectionTitle>O'qish joyi</SectionTitle>
      {editing ? (
        <ProfileEditor me={me} onDone={() => setEditing(false)} />
      ) : (
        <Card className="flex flex-col gap-2 text-[15px]">
          <Row label="Fakultet" value={me.faculty?.name ?? 'Tanlanmagan'} />
          <Row label="Kurs" value={me.course ? `${me.course}-kurs` : '—'} />
          <Row label="Guruh" value={me.group_name ?? '—'} />
          <Row label="A'zo bo'lgan" value={formatDate(me.registered_at)} />
          <Button variant="ghost" onClick={() => setEditing(true)}>
            ✏️ O'zgartirish
          </Button>
        </Card>
      )}

      <div className="grid grid-cols-3 gap-2">
        {[
          { route: '/certificates', label: '🎓 Sertifikatlar', feature: 'certificates' },
          { route: '/achievements', label: '🏅 Yutuqlar', feature: 'achievements' },
          { route: '/rewards', label: "🎁 Sovg'alar", feature: 'rewards' },
        ]
          .filter((item) => me.features[item.feature] !== 'off')
          .map((item) => (
          <button key={item.route} type="button" onClick={() => navigate(item.route)}>
            <Card className="flex items-center justify-center py-3 text-sm font-medium">{item.label}</Card>
          </button>
        ))}
      </div>

      <SectionTitle>Bildirishnomalar</SectionTitle>
      <NotificationsCard />

      {me.is_admin && (
        <Button variant="secondary" onClick={() => window.location.assign('/admin/')}>
          🛠 Admin panel
        </Button>
      )}
    </>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-app-hint">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  )
}
