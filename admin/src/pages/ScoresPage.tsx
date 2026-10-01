import { useEffect, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Pagination, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminUser, Page, RankingRow, ScoreEntry, ScoreSummary, Season } from '../types/api'
import { formatDate, formatDateTime } from '../utils/format'

const LIMIT = 50
export const CATEGORY_LABELS: Record<string, string> = {
  ATTENDANCE: 'Davomat',
  TEST: 'Test',
  TEST_RANK_BONUS: "Testda o'rin",
  BOOK_COMPLETION: 'Kitob',
  CAMPAIGN: 'Kampaniya',
  ACHIEVEMENT: 'Yutuq',
  MANUAL: "Qo'lda",
  REVERSAL: 'Bekor qilish',
}

function MemberPicker({ value, onChange }: { value: AdminUser | null; onChange: (member: AdminUser | null) => void }) {
  const { api } = useSession()
  const [search, setSearch] = useState('')
  const [results, setResults] = useState<AdminUser[]>([])

  useEffect(() => {
    if (search.trim().length < 2) {
      setResults([])
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api<Page<AdminUser>>(`/api/v1/admin/users?limit=8&search=${encodeURIComponent(search.trim())}`, { signal: controller.signal })
        .then((page) => setResults(page.items))
        .catch(() => undefined)
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [search, api])

  if (value) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-app-border px-3 py-2 text-sm">
        <span>
          {value.last_name} {value.first_name} · {value.group_name ?? ''}
        </span>
        <Button variant="ghost" onClick={() => onChange(null)}>
          Boshqa a'zo
        </Button>
      </div>
    )
  }
  return (
    <div className="relative">
      <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="A'zoni qidirish: ism yoki familiya…" />
      {results.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full divide-y divide-app-border rounded-lg border border-app-border bg-app-bg shadow">
          {results.map((user) => (
            <li key={user.id}>
              <button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-app-surface" onClick={() => onChange(user)}>
                {user.last_name} {user.first_name}
                <span className="text-app-hint"> · {user.faculty_name ?? ''} {user.group_name ?? ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function AdjustModal({ member, onClose, onSaved }: { member: AdminUser; onClose: () => void; onSaved: () => void }) {
  const { api } = useSession()
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api('/api/v1/admin/scores/adjust', {
        method: 'POST',
        body: { user_id: member.id, amount: Number(amount), reason: reason.trim() },
      })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={`${member.first_name} ${member.last_name} — ballni tuzatish`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button onClick={() => void save()} loading={busy} disabled={!amount || Number(amount) === 0 || reason.trim().length < 5}>
            Saqlash
          </Button>
        </>
      }
    >
      <Field label="Ball" hint="Qo'shish uchun musbat (5), ayirish uchun manfiy (-5) son yozing">
        <Input type="number" min={-1000} max={1000} value={amount} onChange={(e) => setAmount(e.target.value)} />
      </Field>
      <Field label="Sabab *" hint="Masalan: Texnik nosozlik tasdiqlangani sababli davomat tuzatildi">
        <Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} />
      </Field>
      <p className="text-xs text-app-hint">Har bir tuzatish kim, qachon, nima uchun qilgani bilan audit jurnaliga yoziladi.</p>
      <InlineError message={error} />
    </Modal>
  )
}

function Seasons() {
  const { api, can } = useSession()
  const { state, reload } = useAsync((signal) => api<Season[]>('/api/v1/admin/seasons', { signal }))
  const [form, setForm] = useState({ name: '', starts_on: '', ends_on: '' })
  const [error, setError] = useState<string | null>(null)
  const canManage = can('SEASON_MANAGE')

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h2 className="font-semibold">Mavsumlar</h2>
        <p className="text-sm text-app-hint">
          Yangi mavsum boshlansa, mavsum reytingi noldan boshlanadi. Eski ballar va reytinglar saqlanib qoladi.
        </p>
      </div>
      {state.status === 'success' && (
        <ul className="divide-y divide-app-border text-sm">
          {state.data.length === 0 && <li className="py-2 text-app-hint">Mavsumlar hali yaratilmagan.</li>}
          {state.data.map((season) => (
            <li key={season.id} className="flex items-center justify-between gap-2 py-2">
              <span>
                <span className="font-medium">{season.name}</span>{' '}
                <span className="text-app-hint">
                  {formatDate(season.starts_on)} — {formatDate(season.ends_on)}
                </span>
              </span>
              {season.is_current ? (
                <Badge tone="success">Joriy</Badge>
              ) : (
                canManage && (
                  <Button variant="ghost" onClick={() => void run(() => api(`/api/v1/admin/seasons/${season.id}/activate`, { method: 'POST' }))}>
                    Joriy qilish
                  </Button>
                )
              )}
            </li>
          ))}
        </ul>
      )}
      {canManage && (
        <div className="flex flex-col gap-2 border-t border-app-border pt-3">
          <Field label="Yangi mavsum nomi">
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Masalan: 2026 Kuz" />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Boshlanishi">
              <Input type="date" value={form.starts_on} onChange={(e) => setForm({ ...form, starts_on: e.target.value })} />
            </Field>
            <Field label="Tugashi">
              <Input type="date" value={form.ends_on} onChange={(e) => setForm({ ...form, ends_on: e.target.value })} />
            </Field>
          </div>
          <Button
            disabled={form.name.trim().length < 2 || !form.starts_on || !form.ends_on}
            onClick={() =>
              void run(async () => {
                await api('/api/v1/admin/seasons', { method: 'POST', body: { ...form, make_current: true } })
                setForm({ name: '', starts_on: '', ends_on: '' })
              })
            }
          >
            Yaratish va joriy qilish
          </Button>
        </div>
      )}
      <InlineError message={error} />
    </Card>
  )
}

export function TopMembers({ limit = 10 }: { limit?: number }) {
  const { api } = useSession()
  const { state } = useAsync((signal) => api<{ items: RankingRow[] }>(`/api/v1/rankings?period=all&limit=${limit}`, { signal }))
  if (state.status !== 'success') return null
  return (
    <Card className="p-4">
      <h2 className="font-semibold">🏆 Umumiy reyting — top {limit}</h2>
      <ol className="mt-2 divide-y divide-app-border text-sm">
        {state.data.items.length === 0 && <li className="py-2 text-app-hint">Hali ball to'plaganlar yo'q.</li>}
        {state.data.items.map((row) => (
          <li key={row.rank} className="flex items-center justify-between gap-2 py-1.5">
            <span>
              <span className="inline-block w-6 tabular-nums text-app-hint">{row.rank}.</span> {row.name}
              <span className="text-app-hint"> · {row.group_name ?? ''}</span>
            </span>
            <span className="font-semibold tabular-nums">{row.total}</span>
          </li>
        ))}
      </ol>
    </Card>
  )
}

export function ScoresPage() {
  const { api, can } = useSession()
  const [member, setMember] = useState<AdminUser | null>(null)
  const [offset, setOffset] = useState(0)
  const [adjusting, setAdjusting] = useState(false)
  const canManage = can('SCORE_MANAGE')
  const query = `/api/v1/admin/scores?limit=${LIMIT}&offset=${offset}${member ? `&user_id=${member.id}` : ''}`
  const { state, reload } = useAsync((signal) => api<Page<ScoreEntry>>(query, { signal }), [query])
  const summary = useAsync(
    (signal) =>
      member ? api<ScoreSummary>(`/api/v1/admin/scores/summary?user_id=${member.id}`, { signal }) : Promise.resolve(null),
    [member?.id, state.status === 'success' ? state.data.total : 0],
  )

  async function reverse(entry: ScoreEntry) {
    const reason = window.prompt(`${entry.user_name}: ${entry.amount > 0 ? '+' : ''}${entry.amount} ball bekor qilinadi.\n\nSababini yozing:`)
    if (!reason) return
    try {
      await api(`/api/v1/admin/scores/${entry.id}/reverse`, { method: 'POST', body: { reason } })
      reload()
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    }
  }

  return (
    <>
      <PageHeader
        title="Ballar va reyting"
        subtitle="Ballar faqat tizim tomonidan yoki sababi ko'rsatilgan tuzatish orqali o'zgaradi. O'chirib bo'lmaydi — faqat bekor qilish yozuvi qo'shiladi."
      />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card className="flex flex-col gap-3 p-4">
            <MemberPicker
              value={member}
              onChange={(next) => {
                setMember(next)
                setOffset(0)
              }}
            />
            {member && summary.state.status === 'success' && summary.state.data && (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap gap-2 text-sm">
                  <span className="text-lg font-semibold">Jami: {summary.state.data.total}</span>
                  {Object.entries(summary.state.data.breakdown).map(([category, amount]) => (
                    <Badge key={category}>
                      {CATEGORY_LABELS[category] ?? category}: {amount}
                    </Badge>
                  ))}
                </div>
                {canManage && <Button onClick={() => setAdjusting(true)}>± Ballni tuzatish</Button>}
              </div>
            )}
          </Card>
          <Card>
            {state.status === 'loading' && <LoadingState />}
            {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
            {state.status === 'success' && (
              <>
                <Table head={['Sana', ...(member ? [] : ["A'zo"]), 'Turi', 'Manba / sabab', 'Ball', '']}>
                  {state.data.items.length === 0 && <EmptyRow colSpan={member ? 5 : 6} text="Ball yozuvlari yo'q" />}
                  {state.data.items.map((entry) => (
                    <tr key={entry.id} className={entry.is_reversed ? 'text-app-hint line-through' : ''}>
                      <td className="whitespace-nowrap px-4 py-2">{formatDateTime(entry.created_at)}</td>
                      {!member && <td className="px-4 py-2">{entry.user_name}</td>}
                      <td className="whitespace-nowrap px-4 py-2">{CATEGORY_LABELS[entry.category] ?? entry.category}</td>
                      <td className="max-w-xs px-4 py-2 text-app-hint">{[entry.source_title, entry.reason].filter(Boolean).join(' · ') || '—'}</td>
                      <td className={`px-4 py-2 font-semibold tabular-nums ${entry.amount > 0 ? 'text-emerald-600' : 'text-app-danger'}`}>
                        {entry.amount > 0 ? '+' : ''}
                        {entry.amount}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right">
                        {canManage && entry.category !== 'REVERSAL' && !entry.is_reversed && (
                          <Button variant="ghost" className="text-app-danger" onClick={() => void reverse(entry)}>
                            Bekor qilish
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </Table>
                <Pagination total={state.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
              </>
            )}
          </Card>
        </div>
        <div className="flex flex-col gap-4">
          <TopMembers />
          <Seasons />
        </div>
      </div>
      {adjusting && member && (
        <AdjustModal
          member={member}
          onClose={() => setAdjusting(false)}
          onSaved={() => {
            setAdjusting(false)
            reload()
          }}
        />
      )}
    </>
  )
}
