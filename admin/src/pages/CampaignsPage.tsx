import { useEffect, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import {
  Badge,
  Button,
  Card,
  EmptyRow,
  Field,
  InlineError,
  Input,
  Modal,
  PageHeader,
  Table,
  Textarea,
} from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Book, Page } from '../types/api'
import { formatDate, fromLocalInput, toLocalInput } from '../utils/format'

type Status = 'DRAFT' | 'ACTIVE' | 'COMPLETED' | 'ARCHIVED'

interface Campaign {
  id: string
  name: string
  description: string | null
  starts_at: string
  ends_at: string
  status: Status
  points_per_book: number
  completion_bonus: number
  books: { id: string; title: string; author: string }[]
  participants: number
  verified: number
  event_id: string | null
}

interface Participant {
  user_id: string
  first_name: string
  last_name: string
  member_number: string
  group_name: string | null
  completed_at: string | null
  verified_at: string | null
}

const STATUS: Record<Status, { label: string; tone: 'neutral' | 'success' | 'info' | 'warning' }> = {
  DRAFT: { label: 'Qoralama', tone: 'neutral' },
  ACTIVE: { label: 'Faol', tone: 'success' },
  COMPLETED: { label: 'Yakunlangan', tone: 'info' },
  ARCHIVED: { label: 'Arxivlangan', tone: 'warning' },
}

function CampaignForm({ campaign, onClose, onDone }: { campaign: Campaign | null; onClose: () => void; onDone: () => void }) {
  const { api } = useSession()
  const books = useAsync((signal) => api<Page<Book>>('/api/v1/admin/books?limit=200', { signal }))
  const [name, setName] = useState(campaign?.name ?? '')
  const [description, setDescription] = useState(campaign?.description ?? '')
  const [startsAt, setStartsAt] = useState(toLocalInput(campaign?.starts_at))
  const [endsAt, setEndsAt] = useState(toLocalInput(campaign?.ends_at))
  // A new contest starts from the last-used points (kept on the server); editing keeps its own values.
  const defaults = useAsync((signal) =>
    api<{ points_per_book: number; completion_bonus: number }>('/api/v1/admin/campaigns/defaults', { signal }),
  )
  const [pointsPerBook, setPointsPerBook] = useState(campaign ? String(campaign.points_per_book) : '')
  const [bonus, setBonus] = useState(campaign ? String(campaign.completion_bonus) : '')
  useEffect(() => {
    if (!campaign && defaults.state.status === 'success') {
      const saved = defaults.state.data
      setPointsPerBook((value) => (value === '' ? String(saved.points_per_book) : value))
      setBonus((value) => (value === '' ? String(saved.completion_bonus) : value))
    }
  }, [campaign, defaults.state])
  const [bookIds, setBookIds] = useState<string[]>(campaign?.books.map((b) => b.id) ?? [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggle(id: string) {
    setBookIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]))
  }

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const body = {
        name: name.trim(),
        description: description.trim() || null,
        starts_at: fromLocalInput(startsAt),
        ends_at: fromLocalInput(endsAt),
        points_per_book: Number(pointsPerBook),
        completion_bonus: Number(bonus),
        book_ids: bookIds,
      }
      if (campaign) await api(`/api/v1/admin/campaigns/${campaign.id}`, { method: 'PUT', body })
      else await api('/api/v1/admin/campaigns', { method: 'POST', body })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={campaign ? 'Tanlovni tahrirlash' : 'Yangi kitob tanlovi'} onClose={onClose}>
      <Field label="Nomi" hint="Masalan: «1 hafta — 1 kitob (noyabr, 1-hafta)»">
        <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={160} />
      </Field>
      <Field label="Tavsif (ixtiyoriy)">
        <Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Boshlanishi">
          <Input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
        </Field>
        <Field label="Tugashi">
          <Input type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} />
        </Field>
        <Field label="Kitob uchun ball" hint="O'qib tugatgan a'zoga. Oxirgi qiymat eslab qolinadi — keyingi tanlov shundan boshlanadi.">
          <Input type="number" min={0} max={1000} value={pointsPerBook} onChange={(e) => setPointsPerBook(e.target.value)} />
        </Field>
        <Field label="Yakunlash bonusi" hint="Hammasini o'qiganga qo'shimcha">
          <Input type="number" min={0} max={1000} value={bonus} onChange={(e) => setBonus(e.target.value)} />
        </Field>
      </div>
      <Field label="Kitob(lar)" hint="Bu tanlovning kitobi — boshqa tanlovlarnikidan alohida">
        {books.state.status === 'success' ? (
          <div className="max-h-48 overflow-auto rounded border border-app-border p-2">
            {books.state.data.items.map((book) => (
              <label key={book.id} className="flex items-center gap-2 py-1 text-sm">
                <input type="checkbox" checked={bookIds.includes(book.id)} onChange={() => toggle(book.id)} />
                {book.title} <span className="text-app-hint">— {book.author}</span>
              </label>
            ))}
          </div>
        ) : (
          <LoadingState />
        )}
      </Field>
      <InlineError message={error} />
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Bekor qilish
        </Button>
        <Button loading={busy} disabled={name.trim().length < 2 || bookIds.length === 0 || !startsAt || !endsAt} onClick={() => void submit()}>
          Saqlash
        </Button>
      </div>
    </Modal>
  )
}

function ParticipantsModal({ campaign, onClose }: { campaign: Campaign; onClose: () => void }) {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<Participant[]>(`/api/v1/admin/campaigns/${campaign.id}/participants`, { signal }))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  async function verify(userId: string) {
    setBusy(userId)
    setError(null)
    try {
      await api(`/api/v1/admin/campaigns/${campaign.id}/participants/${userId}/verify`, { method: 'POST' })
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <Modal title={`«${campaign.name}» — qatnashchilar`} onClose={onClose}>
      <InlineError message={error} />
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <Table head={["A'zo", 'Guruh', 'Holat', '']}>
          {state.data.length === 0 && <EmptyRow colSpan={4} text="Hali qatnashchi yo'q" />}
          {state.data.map((p) => (
            <tr key={p.user_id}>
              <td className="px-3 py-2">
                {p.last_name} {p.first_name}
                <p className="font-mono text-xs text-app-hint">{p.member_number}</p>
              </td>
              <td className="px-3 py-2 text-sm">{p.group_name || '—'}</td>
              <td className="px-3 py-2 text-sm">
                {p.verified_at ? '✅ Tasdiqlangan' : p.completed_at ? '⏳ Tekshirilmoqda' : "📖 O'qimoqda"}
              </td>
              <td className="px-3 py-2 text-right">
                {!p.verified_at && (
                  <Button variant="secondary" loading={busy === p.user_id} onClick={() => void verify(p.user_id)}>
                    ✅ Tasdiqlash
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

export function CampaignsPage() {
  const { api, download } = useSession()
  const { state, reload } = useAsync((signal) => api<Campaign[]>('/api/v1/admin/campaigns', { signal }))
  const [editing, setEditing] = useState<Campaign | null | 'new'>(null)
  const [viewing, setViewing] = useState<Campaign | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function act(fn: () => Promise<unknown>, ok?: string) {
    setError(null)
    setMessage(null)
    try {
      await fn()
      if (ok) setMessage(ok)
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    }
  }

  async function report(campaign: Campaign) {
    setError(null)
    try {
      const blob = await download(`/api/v1/admin/campaigns/${campaign.id}/report?format=xlsx`)
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `tanlov-${campaign.name}.xlsx`
      link.click()
      URL.revokeObjectURL(link.href)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Hisobotni yuklab bo'lmadi.")
    }
  }

  return (
    <>
      <PageHeader
        title="Kitob tanlovlari"
        subtitle="«1 hafta — 1 kitob», «1 oy — 1 kitob» va boshqa tanlovlar. Bir nechtasi bir vaqtda ketishi mumkin — har biri o'z kitobi, posti va hisoboti bilan alohida, hech narsa aralashmaydi."
        actions={<Button onClick={() => setEditing('new')}>➕ Yangi tanlov</Button>}
      />
      <InlineError message={error} />
      {message && <p className="text-sm text-emerald-600">{message}</p>}
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' &&
        (state.data.length === 0 ? (
          <Card className="p-6 text-center text-sm text-app-hint">Hali tanlov yaratilmagan.</Card>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {state.data.map((campaign) => (
              <Card key={campaign.id} className="space-y-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">{campaign.name}</p>
                    <p className="text-xs text-app-hint">
                      {formatDate(campaign.starts_at)} — {formatDate(campaign.ends_at)}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <Badge tone={STATUS[campaign.status].tone}>{STATUS[campaign.status].label}</Badge>
                    {campaign.event_id && <Badge tone="info">📅 Tadbirga biriktirilgan</Badge>}
                  </div>
                </div>
                <p className="text-sm">
                  📚 {campaign.books.map((b) => b.title).join(', ') || '—'}
                  <br />
                  🏆 Kitobga {campaign.points_per_book} ball{campaign.completion_bonus ? ` + ${campaign.completion_bonus} bonus` : ''} · 👥{' '}
                  {campaign.participants} qatnashchi · ✅ {campaign.verified} yakunlagan
                </p>
                <div className="flex flex-wrap gap-2">
                  {campaign.status === 'DRAFT' && (
                    <>
                      <Button onClick={() => void act(() => api(`/api/v1/admin/campaigns/${campaign.id}/status`, { method: 'POST', body: { status: 'ACTIVE', announce: true } }), '▶️ Tanlov boshlandi va kanalga e’lon qilindi.')}>
                        ▶️ Boshlash + e'lon
                      </Button>
                      <Button variant="secondary" onClick={() => void act(() => api(`/api/v1/admin/campaigns/${campaign.id}/status`, { method: 'POST', body: { status: 'ACTIVE', announce: false } }), 'Tanlov boshlandi.')}>
                        Boshlash (e'lonsiz)
                      </Button>
                    </>
                  )}
                  {campaign.status === 'ACTIVE' && (
                    <>
                      <Button variant="secondary" onClick={() => void act(() => api(`/api/v1/admin/campaigns/${campaign.id}/announce`, { method: 'POST' }), '📣 Kanalga e’lon qilindi.')}>
                        📣 Kanalga e'lon
                      </Button>
                      <Button variant="secondary" onClick={() => void act(() => api(`/api/v1/admin/campaigns/${campaign.id}/status`, { method: 'POST', body: { status: 'COMPLETED' } }), '🏁 Tanlov yakunlandi.')}>
                        🏁 Yakunlash
                      </Button>
                    </>
                  )}
                  <Button variant="secondary" onClick={() => setViewing(campaign)}>
                    👥 Qatnashchilar
                  </Button>
                  <Button variant="ghost" onClick={() => void report(campaign)}>
                    📄 Hisobot
                  </Button>
                  {campaign.status !== 'COMPLETED' && (
                    <Button variant="ghost" onClick={() => setEditing(campaign)}>
                      ✏️ Tahrirlash
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    className="text-app-danger"
                    onClick={() => {
                      if (window.confirm(`«${campaign.name}» tanlovini o'chirasizmi?`))
                        void act(() => api(`/api/v1/admin/campaigns/${campaign.id}`, { method: 'DELETE' }), "Tanlov o'chirildi.")
                    }}
                  >
                    O'chirish
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        ))}
      {editing && (
        <CampaignForm
          campaign={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onDone={() => {
            setEditing(null)
            setMessage('✓ Saqlandi.')
            reload()
          }}
        />
      )}
      {viewing && <ParticipantsModal campaign={viewing} onClose={() => setViewing(null)} />}
    </>
  )
}
