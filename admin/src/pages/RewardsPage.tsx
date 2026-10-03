import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminReward, AdminUser, RewardCodeRow, RewardRecipient, RewardType, TestPlace, TestWinners } from '../types/api'
import { formatDate, formatDateTime, fromLocalInput, toLocalInput } from '../utils/format'
import { MemberPicker } from './ScoresPage'

export const REWARD_TYPES: Record<RewardType, string> = {
  BOOK: '📚 Kitob',
  CERTIFICATE: '📜 Sertifikat',
  SUBSCRIPTION_CODE: '🔑 Obuna kodi',
  PARTNER_DISCOUNT: '🏷️ Hamkor chegirmasi',
  OTHER: "🎁 Boshqa",
}
const RECIPIENT_STATUS = {
  ASSIGNED: { label: 'Berildi', tone: 'info' },
  DELIVERED: { label: "Kodni ko'rdi", tone: 'warning' },
  REDEEMED: { label: 'Foydalandi', tone: 'success' },
  REVOKED: { label: 'Bekor qilingan', tone: 'neutral' },
} as const
const CODE_STATUS = {
  AVAILABLE: { label: "Bo'sh", tone: 'success' },
  ASSIGNED: { label: 'Berilgan', tone: 'info' },
  REDEEMED: { label: 'Ishlatilgan', tone: 'neutral' },
  EXPIRED: { label: "Muddati o'tgan", tone: 'warning' },
  REVOKED: { label: 'Bekor', tone: 'neutral' },
} as const

function RewardModal({ reward, onClose, onSaved }: { reward: AdminReward | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useSession()
  const [form, setForm] = useState({
    title: reward?.title ?? '',
    description: reward?.description ?? '',
    type: reward?.type ?? 'BOOK',
    value: reward?.value ?? '',
    expires_at: toLocalInput(reward?.expires_at),
    status: reward?.status ?? 'ACTIVE',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [field]: e.target.value })

  async function save() {
    setBusy(true)
    setError(null)
    const body = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      type: form.type,
      value: form.value.trim() || null,
      expires_at: form.expires_at ? fromLocalInput(form.expires_at) : null,
      status: form.status,
    }
    try {
      await api(reward ? `/api/v1/admin/rewards/${reward.id}` : '/api/v1/admin/rewards', { method: reward ? 'PATCH' : 'POST', body })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={reward ? "Sovg'ani tahrirlash" : "Yangi sovg'a"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button loading={busy} disabled={form.title.trim().length < 2} onClick={() => void save()}>
            Saqlash
          </Button>
        </>
      }
    >
      <Field label="Nomi *">
        <Input value={form.title} onChange={set('title')} maxLength={255} placeholder="Masalan: «Kitob olami» do'koniga 20% chegirma" />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Turi">
          <Select value={form.type} onChange={set('type')}>
            {Object.entries(REWARD_TYPES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Qiymati" hint="Masalan: 20%, 1 oylik obuna">
          <Input value={form.value} onChange={set('value')} maxLength={255} />
        </Field>
        <Field label="Amal qilish muddati">
          <Input type="datetime-local" value={form.expires_at} onChange={set('expires_at')} />
        </Field>
        <Field label="Holat">
          <Select value={form.status} onChange={set('status')}>
            <option value="ACTIVE">Faol</option>
            <option value="INACTIVE">Faol emas</option>
            <option value="ARCHIVED">Arxiv</option>
          </Select>
        </Field>
      </div>
      <Field label="Tavsif" hint="A'zo Mini App'da ko'radi: qanday foydalanish, qayerdan olish">
        <Textarea value={form.description} onChange={set('description')} maxLength={3000} rows={3} />
      </Field>
      <InlineError message={error} />
    </Modal>
  )
}

function RewardDetail({ reward, onClose, onChanged }: { reward: AdminReward; onClose: () => void; onChanged: () => void }) {
  const { api } = useSession()
  const codes = useAsync((signal) => api<RewardCodeRow[]>(`/api/v1/admin/rewards/${reward.id}/codes`, { signal }), [reward.id])
  const recipients = useAsync((signal) => api<RewardRecipient[]>(`/api/v1/admin/rewards/${reward.id}/recipients`, { signal }), [reward.id])
  const [newCodes, setNewCodes] = useState('')
  const [member, setMember] = useState<AdminUser | null>(null)
  const [pickerKey, setPickerKey] = useState(0)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function run(action: () => Promise<string | void>) {
    setError(null)
    setMessage(null)
    try {
      const result = await action()
      if (result) setMessage(result)
      codes.reload()
      recipients.reload()
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    }
  }

  return (
    <Modal title={`${REWARD_TYPES[reward.type].split(' ')[0]} ${reward.title}`} onClose={onClose} wide>
      <InlineError message={error} />
      {message && <p className="text-sm text-emerald-600">{message}</p>}
      <Card className="flex flex-col gap-2 p-3">
        <p className="text-sm font-medium">A'zoga berish</p>
        <MemberPicker key={pickerKey} value={member} onChange={setMember} />
        <div className="flex gap-2">
          <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Izoh (masalan: Oktabr oyi yetakchisi)" maxLength={1000} />
          <Button
            disabled={!member}
            onClick={() =>
              void run(async () => {
                const body = { user_id: member?.id, note: note.trim() || null }
                try {
                  await api(`/api/v1/admin/rewards/${reward.id}/assign`, { method: 'POST', body })
                } catch (err) {
                  // The member already has this reward: give it again only if the admin really means it.
                  if (!(err instanceof ApiError && err.code === 'ALREADY_ASSIGNED')) throw err
                  if (!window.confirm(`${member?.last_name} ${member?.first_name} bu sovg'ani avval ham olgan. Yana berilsinmi?`)) return
                  await api(`/api/v1/admin/rewards/${reward.id}/assign`, { method: 'POST', body: { ...body, allow_repeat: true } })
                }
                setMember(null)
                setPickerKey((key) => key + 1)
                setNote('')
                return "✓ Sovg'a berildi, a'zoga bot orqali xabar yuboriladi"
              })
            }
          >
            Berish
          </Button>
        </div>
        {reward.codes_total > 0 && <p className="text-xs text-app-hint">Har bir a'zoga navbatdagi bo'sh kod avtomatik biriktiriladi.</p>}
      </Card>

      <TestWinnersPicker reward={reward} onGiven={(text) => void run(async () => text)} />

      <div>
        <h3 className="mb-2 font-semibold">Oluvchilar</h3>
        {recipients.state.status === 'loading' && <LoadingState />}
        {recipients.state.status === 'success' && (
          <Table head={["A'zo", 'Holat', 'Berilgan', '']}>
            {recipients.state.data.length === 0 && <EmptyRow colSpan={4} text="Hali hech kimga berilmagan" />}
            {recipients.state.data.map((row) => (
              <tr key={row.id}>
                <td className="px-4 py-2">
                  {row.last_name} {row.first_name} <span className="text-xs text-app-hint">{row.group_name ?? ''}</span>
                  {row.note && <p className="text-xs text-app-hint">{row.note}</p>}
                </td>
                <td className="px-4 py-2">
                  <Badge tone={RECIPIENT_STATUS[row.status].tone}>{RECIPIENT_STATUS[row.status].label}</Badge>
                </td>
                <td className="whitespace-nowrap px-4 py-2 text-sm">{formatDateTime(row.assigned_at)}</td>
                <td className="whitespace-nowrap px-4 py-2 text-right">
                  {row.status !== 'REDEEMED' && row.status !== 'REVOKED' && (
                    <Button variant="ghost" onClick={() => void run(async () => void (await api(`/api/v1/admin/user-rewards/${row.id}/status`, { method: 'POST', body: { status: 'REDEEMED' } })))}>
                      Topshirildi
                    </Button>
                  )}
                  {row.status !== 'REVOKED' && (
                    <Button
                      variant="ghost"
                      className="text-app-danger"
                      onClick={() => {
                        const why = window.prompt('Bekor qilish sababi:')
                        if (why) void run(async () => void (await api(`/api/v1/admin/user-rewards/${row.id}/status`, { method: 'POST', body: { status: 'REVOKED', note: why } })))
                      }}
                    >
                      Bekor
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="font-semibold">Promo-kodlar</h3>
        <p className="text-xs text-app-hint">
          Faqat hamkorlar bergan haqiqiy kodlarni kiriting. Kodlar shifrlangan holda saqlanadi, adminlarga yashirin ko'rinadi va faqat oluvchi a'zoga ochiladi.
        </p>
        <Textarea value={newCodes} onChange={(e) => setNewCodes(e.target.value)} rows={3} placeholder={'Har bir qatorga bitta kod\nKITOB-AB12CD\nKITOB-EF34GH'} className="font-mono text-sm" />
        <div className="flex justify-end">
          <Button
            variant="secondary"
            disabled={!newCodes.trim()}
            onClick={() =>
              void run(async () => {
                const result = await api<{ added: number; duplicates: number }>(`/api/v1/admin/rewards/${reward.id}/codes`, {
                  method: 'POST',
                  body: { codes: newCodes.split('\n') },
                })
                setNewCodes('')
                return `✓ ${result.added} ta kod qo'shildi${result.duplicates ? `, ${result.duplicates} tasi takror edi` : ''}`
              })
            }
          >
            Kodlarni qo'shish
          </Button>
        </div>
        {codes.state.status === 'success' && codes.state.data.length > 0 && (
          <Table head={['Kod', 'Holat', 'Kimga', 'Muddat', '']}>
            {codes.state.data.map((code) => (
              <tr key={code.id}>
                <td className="px-4 py-2 font-mono">{code.masked}</td>
                <td className="px-4 py-2">
                  <Badge tone={CODE_STATUS[code.status].tone}>{CODE_STATUS[code.status].label}</Badge>
                </td>
                <td className="px-4 py-2 text-sm">{code.assigned_to ?? '—'}</td>
                <td className="px-4 py-2 text-sm">{code.expires_at ? formatDate(code.expires_at) : '—'}</td>
                <td className="px-4 py-2 text-right">
                  {code.status === 'AVAILABLE' && (
                    <Button variant="ghost" className="text-app-danger" onClick={() => void run(async () => void (await api(`/api/v1/admin/rewards/${reward.id}/codes/${code.id}/revoke`, { method: 'POST' })))}>
                      Olib tashlash
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </div>
    </Modal>
  )
}

const MEDAL: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }

/** Places 1-3 of every recent test: give this reward to a place, once per place (any reward counts). */
function TestWinnersPicker({ reward, onGiven }: { reward: AdminReward; onGiven: (text: string) => void }) {
  const { api } = useSession()
  const winners = useAsync((signal) => api<TestWinners[]>('/api/v1/admin/rewards/test-winners?days=90', { signal }))
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function give(test: TestWinners, place: TestPlace) {
    if (!window.confirm(`«${reward.title}» → ${place.name} («${test.title}», ${place.place}-o'rin)?`)) return
    setBusy(`${test.test_id}:${place.place}`)
    setError(null)
    try {
      await api(`/api/v1/admin/rewards/${reward.id}/assign-test-place`, { method: 'POST', body: { test_id: test.test_id, place: place.place } })
      winners.reload()
      onGiven(`✓ ${place.name} ga berildi («${test.title}», ${place.place}-o'rin)`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card className="flex flex-col gap-2 p-3">
      <p className="text-sm font-medium">📝 Test g'oliblari (oxirgi 90 kun)</p>
      <p className="text-xs text-app-hint">
        Har bir testning 1-, 2-, 3-o'rinlari (tadbir testida — faqat qatnashganlar). Sovg'a berilgan o'rin «✅ berilgan» bo'lib qoladi — adashib ikki marta
        berib bo'lmaydi.
      </p>
      <InlineError message={error} />
      {winners.state.status === 'loading' && <LoadingState />}
      {winners.state.status === 'success' && winners.state.data.length === 0 && (
        <p className="text-sm text-app-hint">Yaqinda yopilgan test yo'q.</p>
      )}
      {winners.state.status === 'success' &&
        winners.state.data.map((test) => (
          <div key={test.test_id} className="rounded-lg border border-app-border p-2">
            <p className="text-sm font-semibold">
              «{test.title}»{test.event_title && <span className="font-normal text-app-hint"> · {test.event_title}</span>}
              <span className="font-normal text-app-hint"> · {formatDate(test.closed_at)}</span>
            </p>
            <ul className="mt-1 flex flex-col gap-1">
              {test.places.map((place) => (
                <li key={place.place} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span>
                    {MEDAL[place.place]} {place.name} <span className="text-xs text-app-hint">{place.group_name ?? ''} · {place.score}/{place.max_score}</span>
                  </span>
                  {place.given_reward ? (
                    <Badge tone="success">✅ berilgan: {place.given_reward}</Badge>
                  ) : (
                    <Button
                      variant="secondary"
                      className="px-3 py-1 text-sm"
                      loading={busy === `${test.test_id}:${place.place}`}
                      disabled={busy !== null}
                      onClick={() => void give(test, place)}
                    >
                      🎁 Berish
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
    </Card>
  )
}

export function RewardsPage() {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<AdminReward[]>('/api/v1/admin/rewards', { signal }))
  const [editing, setEditing] = useState<AdminReward | 'new' | null>(null)
  const [open, setOpen] = useState<AdminReward | null>(null)

  return (
    <>
      <PageHeader
        title="Sovg'alar"
        subtitle="Faol a'zolarni taqdirlash: kitob, sertifikat, hamkor chegirmasi yoki obuna kodi. Har bir berish audit jurnaliga yoziladi."
        actions={<Button onClick={() => setEditing('new')}>+ Yangi sovg'a</Button>}
      />
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={["Sovg'a", 'Turi', 'Kodlar (bo\'sh/jami)', 'Oluvchilar', 'Muddat', '']}>
            {state.data.length === 0 && <EmptyRow colSpan={6} text="Sovg'alar hali qo'shilmagan" />}
            {state.data.map((reward) => (
              <tr key={reward.id} className={reward.status === 'ACTIVE' ? '' : 'text-app-hint'}>
                <td className="px-4 py-2.5">
                  <p className="font-medium">
                    {reward.title} {reward.status !== 'ACTIVE' && <Badge>{reward.status === 'INACTIVE' ? 'faol emas' : 'arxiv'}</Badge>}
                  </p>
                  {reward.value && <p className="text-xs text-app-hint">{reward.value}</p>}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm">{REWARD_TYPES[reward.type]}</td>
                <td className="px-4 py-2.5 tabular-nums">{reward.codes_total ? `${reward.codes_available} / ${reward.codes_total}` : '—'}</td>
                <td className="px-4 py-2.5 tabular-nums">{reward.recipients}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm">{reward.expires_at ? formatDate(reward.expires_at) : '—'}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  <Button variant="ghost" onClick={() => setOpen(reward)}>
                    Berish va kodlar
                  </Button>
                  <Button variant="ghost" onClick={() => setEditing(reward)}>
                    Tahrirlash
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {editing && (
        <RewardModal
          reward={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
      {open && <RewardDetail reward={open} onClose={() => setOpen(null)} onChanged={reload} />}
    </>
  )
}
