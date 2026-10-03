import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { SystemStatusCard } from '../components/SystemStatus'
import { Button, Card, InlineError, Input, PageHeader, Select } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Setting } from '../types/api'

const GROUP_TITLES: Record<string, string> = {
  score: '🏆 Ball qoidalari',
  registration: "📝 Ro'yxatdan o'tish",
  attendance: '✅ Davomat',
  notifications: '🔔 Bildirishnomalar',
  org: '🏛 Tashkilot (rasmiy hisobotlar uchun)',
  certificates: '🎓 Sertifikatlar',
  payments: "💳 Karta orqali to'lov",
  premium: '💎 Premium',
  referral: "👥 Do'stlarni taklif qilish",
  channel: '📣 Telegram kanal',
  ranking: '📊 Reyting',
}

function toText(setting: Setting, value: unknown): string {
  if (setting.kind === 'int_list') return (value as number[]).join(', ')
  if (setting.kind === 'bool') return value ? 'true' : 'false'
  return String(value ?? '')
}

function fromText(setting: Setting, text: string): unknown {
  switch (setting.kind) {
    case 'int':
      return Number(text)
    case 'bool':
      return text === 'true'
    case 'int_list':
      return text
        .split(',')
        .map((part) => part.trim())
        .filter(Boolean)
        .map(Number)
    default:
      return text
  }
}

function SettingRow({ setting, canEdit }: { setting: Setting; canEdit: boolean }) {
  const { api } = useSession()
  const [current, setCurrent] = useState<unknown>(setting.value)
  const [text, setText] = useState(toText(setting, setting.value))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const dirty = text !== toText(setting, current)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const result = await api<Setting>(`/api/v1/admin/settings/${setting.key}`, {
        method: 'PUT',
        body: { value: fromText(setting, text) },
      })
      setCurrent(result.value)
      setText(toText(setting, result.value))
      setSaved(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  let input
  if (setting.kind === 'bool') {
    input = (
      <Select
        value={text}
        disabled={!canEdit}
        onChange={(e) => {
          setText(e.target.value)
          setSaved(false)
        }}
      >
        <option value="true">Ha</option>
        <option value="false">Yo'q</option>
      </Select>
    )
  } else if (setting.kind === 'choice') {
    input = (
      <Select value={text} disabled={!canEdit} onChange={(e) => setText(e.target.value)}>
        {setting.choices.map((choice) => (
          <option key={choice} value={choice}>
            {choice}
          </option>
        ))}
      </Select>
    )
  } else {
    input = (
      <Input
        type={setting.kind === 'int' ? 'number' : setting.kind === 'time' ? 'time' : 'text'}
        value={text}
        disabled={!canEdit}
        onChange={(e) => {
          setText(e.target.value)
          setSaved(false)
        }}
      />
    )
  }

  return (
    <div className="grid gap-2 px-4 py-3 md:grid-cols-[1fr_16rem_auto] md:items-center">
      <div>
        <p className="text-sm font-medium">{setting.description}</p>
        <p className="text-xs text-app-hint">
          Standart qiymat: {toText(setting, setting.default) || '—'}
          {setting.kind === 'int_list' && ' (vergul bilan ajrating)'}
        </p>
        <InlineError message={error} />
      </div>
      {input}
      {canEdit && (
        <Button variant={dirty ? 'primary' : 'secondary'} disabled={!dirty} loading={busy} onClick={() => void save()}>
          {saved && !dirty ? '✓ Saqlandi' : 'Saqlash'}
        </Button>
      )}
    </div>
  )
}

export function SettingsPage() {
  const { api, can } = useSession()
  const canEdit = can('SETTINGS_MANAGE')
  const { state, reload } = useAsync((signal) => api<Setting[]>('/api/v1/admin/settings', { signal }))

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const groups = [...new Set(state.data.map((setting) => setting.group))]

  return (
    <>
      <PageHeader
        title="Sozlamalar"
        subtitle={
          canEdit
            ? "Har bir o'zgarish audit jurnaliga yoziladi. Ballarni o'zgartirish faqat keyingi hisoblarga ta'sir qiladi."
            : "Sozlamalarni o'zgartirish uchun «SETTINGS_MANAGE» ruxsati kerak."
        }
      />
      {canEdit && <SystemStatusCard />}
      {groups.map((group) => (
        <Card key={group}>
          <h2 className="border-b border-app-border px-4 py-3 font-semibold">{GROUP_TITLES[group] ?? group}</h2>
          <div className="divide-y divide-app-border">
            {state.data
              .filter((setting) => setting.group === group)
              .map((setting) => (
                <SettingRow key={setting.key} setting={setting} canEdit={canEdit} />
              ))}
          </div>
        </Card>
      ))}
    </>
  )
}
