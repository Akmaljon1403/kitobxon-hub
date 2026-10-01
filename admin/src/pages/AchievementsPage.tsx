import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AchievementHolder, AdminAchievement, AdminUser } from '../types/api'
import { formatDateTime } from '../utils/format'
import { MemberPicker } from './ScoresPage'

export const CRITERIA_LABELS: Record<string, string> = {
  BOOKS_COMPLETED: "O'qilgan (tasdiqlangan) kitoblar soni",
  EVENTS_ATTENDED: 'Qatnashgan tadbirlar soni',
  TESTS_PASSED: "Muvaffaqiyatli topshirilgan testlar soni",
  PERFECT_TESTS: 'Maksimal ball olingan testlar soni',
  ACTIVITY_STREAK_WEEKS: 'Ketma-ket faol haftalar (tadbir yoki test)',
  MONTHLY_TOP_RANK: "O'tgan oy reytingida shu o'ringacha",
  MANUAL: 'Faqat admin beradi',
}

function EditModal({ achievement, onClose, onSaved }: { achievement: AdminAchievement | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useSession()
  const [form, setForm] = useState({
    code: achievement?.code ?? '',
    criteria: achievement?.criteria ?? 'MANUAL',
    title: achievement?.title ?? '',
    description: achievement?.description ?? '',
    icon: achievement?.icon ?? '🏅',
    threshold: String(achievement?.threshold ?? 1),
    points: String(achievement?.points ?? 0),
    sort_order: String(achievement?.sort_order ?? 100),
    is_active: achievement?.is_active ?? true,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [field]: e.target.value })

  async function save() {
    setBusy(true)
    setError(null)
    const common = {
      title: form.title.trim(),
      description: form.description.trim(),
      icon: form.icon.trim() || '🏅',
      threshold: Number(form.threshold),
      points: Number(form.points),
      sort_order: Number(form.sort_order),
      is_active: form.is_active,
    }
    try {
      if (achievement) {
        await api(`/api/v1/admin/achievements/${achievement.id}`, { method: 'PATCH', body: common })
      } else {
        await api('/api/v1/admin/achievements', {
          method: 'POST',
          body: { ...common, code: form.code.trim().toUpperCase(), criteria: form.criteria },
        })
      }
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={achievement ? `${achievement.icon} ${achievement.title}` : 'Yangi yutuq'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button loading={busy} disabled={form.title.trim().length < 2 || form.description.trim().length < 2 || (!achievement && form.code.trim().length < 3)} onClick={() => void save()}>
            Saqlash
          </Button>
        </>
      }
    >
      {!achievement && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Kod *" hint="Lotin harflari, raqam va _ (masalan: BEST_READER)">
            <Input value={form.code} onChange={set('code')} maxLength={64} />
          </Field>
          <Field label="Qanday olinadi *">
            <Select value={form.criteria} onChange={set('criteria')}>
              {Object.entries(CRITERIA_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      )}
      {achievement && <p className="text-sm text-app-hint">Qanday olinadi: {CRITERIA_LABELS[achievement.criteria] ?? achievement.criteria}</p>}
      <div className="grid gap-3 sm:grid-cols-[5rem_1fr]">
        <Field label="Belgi">
          <Input value={form.icon} onChange={set('icon')} maxLength={16} className="text-center text-xl" />
        </Field>
        <Field label="Nomi *">
          <Input value={form.title} onChange={set('title')} maxLength={128} />
        </Field>
      </div>
      <Field label="Tavsif *" hint="A'zo Mini App'da ko'radi">
        <Textarea value={form.description} onChange={set('description')} maxLength={1000} rows={2} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Chegara" hint={form.criteria === 'MONTHLY_TOP_RANK' ? "Shu o'ringacha" : 'Nechta kerak'}>
          <Input type="number" min={1} max={1000} value={form.threshold} onChange={set('threshold')} disabled={form.criteria === 'MANUAL'} />
        </Field>
        <Field label="Bonus ball" hint="0 — ballsiz">
          <Input type="number" min={0} max={1000} value={form.points} onChange={set('points')} />
        </Field>
        <Field label="Tartib">
          <Input type="number" min={0} value={form.sort_order} onChange={set('sort_order')} />
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
        Faol (o'chirilsa, yangi a'zolar ololmaydi; olganlar saqlanadi)
      </label>
      <p className="text-xs text-app-hint">Chegarani o'zgartirish allaqachon berilgan yutuqlarni bekor qilmaydi.</p>
      <InlineError message={error} />
    </Modal>
  )
}

function HoldersModal({ achievement, onClose, onChanged }: { achievement: AdminAchievement; onClose: () => void; onChanged: () => void }) {
  const { api, can } = useSession()
  const { state, reload } = useAsync(
    (signal) => api<AchievementHolder[]>(`/api/v1/admin/achievements/${achievement.id}/holders`, { signal }),
    [achievement.id],
  )
  const [member, setMember] = useState<AdminUser | null>(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const canManage = can('SCORE_MANAGE')

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      reload()
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    }
  }

  return (
    <Modal title={`${achievement.icon} ${achievement.title} — egalari`} onClose={onClose} wide>
      {canManage && (
        <Card className="flex flex-col gap-2 p-3">
          <p className="text-sm font-medium">Qo'lda berish</p>
          <MemberPicker value={member} onChange={setMember} />
          <div className="flex gap-2">
            <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Sabab (masalan: ko'rgazmani tashkil qildi)" />
            <Button
              disabled={!member || reason.trim().length < 5}
              onClick={() =>
                void run(async () => {
                  await api(`/api/v1/admin/achievements/${achievement.id}/grant`, {
                    method: 'POST',
                    body: { user_id: member?.id, reason: reason.trim() },
                  })
                  setMember(null)
                  setReason('')
                })
              }
            >
              Berish
            </Button>
          </div>
        </Card>
      )}
      <InlineError message={error} />
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <Table head={["A'zo", 'Guruh', 'Sana', '']}>
          {state.data.length === 0 && <EmptyRow colSpan={4} text="Hali hech kim olmagan" />}
          {state.data.map((holder) => (
            <tr key={holder.id}>
              <td className="px-4 py-2">
                {holder.last_name} {holder.first_name} {holder.granted && <Badge tone="info">admin bergan</Badge>}
              </td>
              <td className="px-4 py-2">{holder.group_name ?? '—'}</td>
              <td className="whitespace-nowrap px-4 py-2">{formatDateTime(holder.unlocked_at)}</td>
              <td className="px-4 py-2 text-right">
                {canManage && (
                  <Button
                    variant="ghost"
                    className="text-app-danger"
                    onClick={() => {
                      const why = window.prompt('Yutuqni bekor qilish sababi:')
                      if (why && why.trim().length >= 5)
                        void run(() => api(`/api/v1/admin/user-achievements/${holder.id}/revoke`, { method: 'POST', body: { reason: why.trim() } }))
                    }}
                  >
                    Bekor qilish
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </Modal>
  )
}

export function AchievementsPage() {
  const { api, can } = useSession()
  const { state, reload } = useAsync((signal) => api<AdminAchievement[]>('/api/v1/admin/achievements', { signal }))
  const [editing, setEditing] = useState<AdminAchievement | 'new' | null>(null)
  const [holders, setHolders] = useState<AdminAchievement | null>(null)
  const canEdit = can('SETTINGS_MANAGE')

  return (
    <>
      <PageHeader
        title="Yutuqlar"
        subtitle="Yutuqlar tasdiqlangan faollik asosida avtomatik beriladi: davomat, testlar, tasdiqlangan kitoblar, faol haftalar, oylik reyting."
        actions={canEdit && <Button onClick={() => setEditing('new')}>+ Yangi yutuq</Button>}
      />
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={['Yutuq', 'Qanday olinadi', 'Bonus', 'Egalari', '']}>
            {state.data.length === 0 && <EmptyRow colSpan={5} text="Yutuqlar yo'q" />}
            {state.data.map((achievement) => (
              <tr key={achievement.id} className={achievement.is_active ? '' : 'text-app-hint'}>
                <td className="px-4 py-2.5">
                  <p className="font-medium">
                    <span className="mr-1 text-lg">{achievement.icon}</span> {achievement.title} {!achievement.is_active && <Badge>o'chirilgan</Badge>}
                  </p>
                  <p className="text-xs text-app-hint">{achievement.description}</p>
                </td>
                <td className="px-4 py-2.5 text-sm">
                  {CRITERIA_LABELS[achievement.criteria] ?? achievement.criteria}
                  {achievement.criteria !== 'MANUAL' && <span className="font-semibold">: {achievement.threshold}</span>}
                </td>
                <td className="px-4 py-2.5 tabular-nums">{achievement.points > 0 ? `+${achievement.points}` : '—'}</td>
                <td className="px-4 py-2.5 tabular-nums">{achievement.holders}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  <Button variant="ghost" onClick={() => setHolders(achievement)}>
                    Egalari
                  </Button>
                  {canEdit && (
                    <Button variant="ghost" onClick={() => setEditing(achievement)}>
                      Tahrirlash
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {editing && (
        <EditModal
          achievement={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
      {holders && <HoldersModal achievement={holders} onClose={() => setHolders(null)} onChanged={reload} />}
    </>
  )
}
