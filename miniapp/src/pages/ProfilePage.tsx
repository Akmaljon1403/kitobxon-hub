import { useState } from 'react'

import { Avatar } from '../components/Avatar'
import { Icon, type IconName } from '../components/Icon'
import { FeatureLocked } from '../components/FeatureGate'
import { PassportCard } from '../components/PassportCard'
import { InviteCard } from '../components/InviteCard'
import { PortfolioCard } from '../components/PortfolioCard'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, FeatureTile, SectionTitle, Toggle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Faculty, Me, NotificationSettings } from '../types/api'
import { formatDate } from '../utils/format'
import { useHomeBackButton } from '../hooks/useBackButton'
import { navigate } from '../utils/router'
import { BenefitCard } from '../components/BenefitCard'
import { haptic } from '../utils/telegram'

const NOTIFICATION_LABELS: Record<keyof NotificationSettings, { icon: IconName; text: string }> = {
  event_reminders: { icon: 'calendar', text: 'Tadbir eslatmalari' },
  test_reminders: { icon: 'file-text', text: 'Test eslatmalari' },
  reading_reminders: { icon: 'book-open', text: "O'qish muddati eslatmalari" },
  quote_of_day: { icon: 'quote', text: 'Kun iqtibosi' },
  ranking_updates: { icon: 'trophy', text: 'Reyting yangiliklari' },
  achievement_alerts: { icon: 'medal', text: 'Yutuqlar haqida' },
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

  const fieldClass = 'mt-1 w-full rounded-xl bg-app-surface px-3 py-3 text-[15px] outline-none transition focus:ring-2 focus:ring-brand-400/50'
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
          label={NOTIFICATION_LABELS[field].text}
          icon={NOTIFICATION_LABELS[field].icon}
          checked={settings[field]}
          disabled={busy}
          onChange={(value) => change(field, value)}
        />
      ))}
    </Card>
  )
}

export function ProfilePage() {
  useHomeBackButton()
  const { me } = useAuth()
  const [editing, setEditing] = useState(false)
  if (!me) return null

  return (
    <>
      <Card className="flex flex-col items-center gap-2 text-center">
        <Avatar me={me} size="size-20" />
        <h1 className="font-serif text-2xl font-bold">
          {me.first_name} {me.last_name}
        </h1>
        {me.telegram_username && <p className="text-sm text-app-hint">@{me.telegram_username}</p>}
        {me.is_admin && <Badge tone="info">Administrator</Badge>}
      </Card>

      {(me.features.premium !== 'off' || me.is_premium) && (
        <button type="button" className="w-full text-left" onClick={() => navigate('/premium')}>
          <Card interactive className="flex items-center gap-2.5 py-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-gold-400/15 text-gold-500 dark:text-gold-300">
              <Icon name="gem" size={18} />
            </span>
            <span className="flex-1 text-[15px] font-medium">
              {me.premium_lifetime
                ? "Umrbod Premium a'zo"
                : me.is_premium
                  ? `Premium a'zo — ${formatDate(me.premium_until)} gacha`
                  : 'Premium obuna'}
            </span>
            <Icon name="chevron-right" size={18} className="shrink-0 text-app-hint" />
          </Card>
        </button>
      )}

      {me.features.passport === 'on' ? (
        <PassportCard />
      ) : (
        me.features.passport === 'premium' && <FeatureLocked code="passport" access="premium" />
      )}

      <PortfolioCard />

      <InviteCard />

      <SectionTitle>O'qish joyi</SectionTitle>
      {editing ? (
        <ProfileEditor me={me} onDone={() => setEditing(false)} />
      ) : (
        <Card className="flex flex-col gap-2 text-[15px]">
          <Row label="Fakultet" value={me.faculty?.name ?? 'Tanlanmagan'} />
          <Row label="Kurs" value={me.graduated ? 'Bitiruvchi' : me.course ? `${me.course}-kurs` : '—'} icon={me.graduated ? 'graduation-cap' : undefined} />
          <Row label="Guruh" value={me.group_name ?? '—'} />
          <Row label="A'zo bo'lgan" value={formatDate(me.registered_at)} />
          <Button variant="ghost" onClick={() => setEditing(true)}>
            <Icon name="pencil" size={16} /> O'zgartirish
          </Button>
        </Card>
      )}

      <BenefitCard />

      <button type="button" className="w-full text-left" onClick={() => navigate('/services')}>
        <Card interactive className="flex items-center gap-3">
          <FeatureTile icon="grid" tone="hint" />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">Barcha xizmatlar</p>
            <p className="truncate text-sm text-app-hint">Javon, missiyalar, yutuqlar, sovg‘alar, sertifikatlar, liga va boshqalar</p>
          </div>
          <Icon name="chevron-right" className="shrink-0 text-app-hint" />
        </Card>
      </button>

      <SectionTitle>Bildirishnomalar</SectionTitle>
      <NotificationsCard />

      <Button variant="secondary" onClick={() => navigate('/help')}>
        <Icon name="help-circle" size={18} /> Yordam, savol-javoblar va adminga yozish
      </Button>

      {me.is_admin && (
        <Button variant="secondary" onClick={() => window.location.assign('/admin/')}>
          <Icon name="settings" size={18} /> Admin panel
        </Button>
      )}
    </>
  )
}

function Row({ label, value, icon }: { label: string; value: string; icon?: IconName }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-app-hint">{label}</span>
      <span className="flex items-center gap-1.5 text-right font-medium">
        {icon && <Icon name={icon} size={15} className="shrink-0 text-app-hint" />}
        {value}
      </span>
    </div>
  )
}
