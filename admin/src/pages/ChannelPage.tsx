import { useRef, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { ChannelOverview, ChannelPost, ChannelPostKind } from '../types/api'
import { formatDateTime, fromLocalInput } from '../utils/format'
import { navigate } from '../utils/router'

const KINDS: Record<ChannelPostKind, string> = {
  EVENT: '📅 Tadbir',
  EVENT_REMINDER: '⏰ Eslatma',
  BOOK: '📚 Kitob',
  READING_NUDGE: "📖 O'qishga undov",
  QUOTE: '💬 Iqtibos',
  RESULTS: "🏆 G'oliblar",
  INVITE: '📲 Taklif',
  MANUAL: "✍️ Qo'lda",
}
const STATUS = {
  PENDING: { label: 'Navbatda', tone: 'info' },
  SENT: { label: 'Joylandi', tone: 'success' },
  FAILED: { label: 'Xato', tone: 'danger' },
  CANCELLED: { label: 'Bekor', tone: 'neutral' },
} as const

/** Telegram HTML of a post as plain text for the list. */
function plain(text: string): string {
  const element = document.createElement('div')
  element.innerHTML = text.replace(/<br\s*\/?>/g, '\n')
  return element.textContent ?? ''
}

function Composer({ overview, onSent }: { overview: ChannelOverview; onSent: () => void }) {
  const { api } = useSession()
  const [text, setText] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [stickerId, setStickerId] = useState('')
  const [withButton, setWithButton] = useState(true)
  const [later, setLater] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  async function send() {
    setBusy(true)
    setError(null)
    setNotice(null)
    const form = new FormData()
    form.append('text', text)
    if (photo) form.append('photo', photo)
    if (stickerId) form.append('sticker_id', stickerId)
    form.append('with_button', String(withButton))
    const when = later ? fromLocalInput(later) : null
    if (when) form.append('scheduled_at', when)
    try {
      await api('/api/v1/admin/channel/posts', { method: 'POST', body: form })
      setText('')
      setPhoto(null)
      setStickerId('')
      setLater('')
      setNotice(when ? '✅ Post rejalashtirildi.' : '✅ Post navbatga qo‘yildi — bir necha soniyada kanalda chiqadi.')
      onSent()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <h2 className="font-semibold">✍️ Kanalga post yozish</h2>
      <Field label="Matn" hint="Masalan: «Shanba kuni soat 15:00 da «O'tkan kunlar» muhokamasi. Asarni o'qib keling!»">
        <Textarea rows={5} maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Rasm (ixtiyoriy)">
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => fileInput.current?.click()}>
              📷 {photo ? 'Boshqa rasm' : 'Rasm tanlash'}
            </Button>
            {photo && (
              <span className="truncate text-sm">
                {photo.name}{' '}
                <button type="button" className="text-app-danger" onClick={() => setPhoto(null)}>
                  ×
                </button>
              </span>
            )}
          </div>
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              setPhoto(e.target.files?.[0] ?? null)
              e.target.value = ''
            }}
          />
        </Field>
        <Field label="Stiker (ixtiyoriy)" hint={overview.stickers.length ? undefined : 'Botda /stiker buyrug‘i bilan stikerlar qo‘shing'}>
          <Select value={stickerId} onChange={(e) => setStickerId(e.target.value)} disabled={!overview.stickers.length}>
            <option value="">— stikersiz —</option>
            {overview.stickers.map((sticker, index) => (
              <option key={sticker.id} value={sticker.id}>
                {sticker.emoji ?? '🙂'} {sticker.set_name ?? `Stiker ${index + 1}`}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Qachon" hint="Bo'sh qoldirilsa — hozir">
          <Input type="datetime-local" value={later} onChange={(e) => setLater(e.target.value)} />
        </Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm">
          <input type="checkbox" className="size-4" checked={withButton} onChange={(e) => setWithButton(e.target.checked)} />
          «📲 Botga qo'shilish» tugmasi
        </label>
      </div>
      <InlineError message={error} />
      {notice && <p className="text-sm text-app-link">{notice}</p>}
      <div>
        <Button loading={busy} disabled={!text.trim() && !photo} onClick={() => void send()}>
          {later ? '🗓 Rejalashtirish' : '📢 Kanalga joylash'}
        </Button>
      </div>
    </Card>
  )
}

export function ChannelPage() {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<ChannelOverview>('/api/v1/admin/channel', { signal }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function act(work: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await work()
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bajarib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const overview = state.data

  return (
    <>
      <PageHeader
        title="Telegram kanal"
        subtitle="Bot kanalga o'zi post joylaydi: yangi tadbir va kitoblar, «ertaga ... o'qib kelamiz» eslatmalari, o'qishga undovlar, kun iqtibosi, g'oliblar va botga taklif."
        actions={
          <Button variant="secondary" loading={busy} disabled={!overview.chat_id} onClick={() => void act(() => api('/api/v1/admin/channel/test', { method: 'POST' }))}>
            🧪 Sinov posti
          </Button>
        }
      />
      <Card className="flex flex-col gap-2 p-4 text-sm">
        <p>
          Kanal:{' '}
          {overview.link ? (
            <a className="text-app-link underline" href={overview.link} target="_blank" rel="noreferrer">
              {overview.chat_id}
            </a>
          ) : (
            <b>{overview.chat_id ?? 'kiritilmagan'}</b>
          )}{' '}
          · {overview.enabled ? <Badge tone="success">Yoqilgan</Badge> : <Badge tone="warning">O'chiq</Badge>} · navbatda: {overview.pending} · oxirgi post:{' '}
          {overview.last_sent_at ? formatDateTime(overview.last_sent_at) : '—'}
        </p>
        {!overview.enabled && (
          <p className="text-app-hint">
            Yoqish: 1) Telegram'da kanal → Administratorlar → botni qo'shing va «Xabar joylash» huquqini bering. 2){' '}
            <button type="button" className="text-app-link underline" onClick={() => navigate('/settings')}>
              Sozlamalar → 📣 Telegram kanal
            </button>{' '}
            → «Bot klub kanaliga post joylaydi» ni yoqing. 3) «🧪 Sinov posti» bilan tekshiring.
          </p>
        )}
        {overview.last_error && <p className="text-app-danger">⚠️ Oxirgi xato: {overview.last_error}. Bot kanalga admin qilinganini tekshiring.</p>}
        <InlineError message={error} />
      </Card>

      <Composer overview={overview} onSent={reload} />

      <Card>
        <h2 className="border-b border-app-border px-4 py-3 font-semibold">So'nggi postlar</h2>
        <Table head={['Turi', 'Matn', 'Vaqt', 'Holat', '']}>
          {overview.posts.length === 0 && <EmptyRow colSpan={5} text="Hali post yo'q" />}
          {overview.posts.map((post: ChannelPost) => (
            <tr key={post.id} className={post.status === 'CANCELLED' ? 'text-app-hint' : ''}>
              <td className="whitespace-nowrap px-4 py-2 text-sm">{KINDS[post.kind]}</td>
              <td className="max-w-md px-4 py-2 text-sm">
                <p className="line-clamp-3 whitespace-pre-line">{plain(post.text) || '🖼 (rasm)'}</p>
                <p className="text-xs text-app-hint">
                  {post.has_photo && '🖼 rasm '}
                  {post.has_sticker && '🎨 stiker'}
                </p>
                {post.last_error && post.status !== 'SENT' && <p className="text-xs text-app-danger">{post.last_error}</p>}
              </td>
              <td className="whitespace-nowrap px-4 py-2 text-sm">{formatDateTime(post.sent_at ?? post.scheduled_at)}</td>
              <td className="px-4 py-2">
                <Badge tone={STATUS[post.status].tone}>{STATUS[post.status].label}</Badge>
              </td>
              <td className="px-4 py-2 text-right">
                {post.status === 'PENDING' && (
                  <Button variant="ghost" className="text-app-danger" disabled={busy} onClick={() => void act(() => api(`/api/v1/admin/channel/posts/${post.id}/cancel`, { method: 'POST' }))}>
                    Bekor qilish
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      </Card>

      <Card className="flex flex-col gap-2 p-4">
        <h2 className="font-semibold">🎨 Stikerlar ({overview.stickers.length})</h2>
        <p className="text-sm text-app-hint">
          Botga <b>/stiker</b> deb yozing va yoqqan stikerlarni yuboring (animatsion stikerlar ham bo'ladi). Avtomatik postlardan keyin ulardan biri tasodifiy qo'shiladi.
        </p>
        <div className="flex flex-wrap gap-2">
          {overview.stickers.map((sticker, index) => (
            <span key={sticker.id} className="flex items-center gap-1 rounded-full border border-app-border px-3 py-1 text-sm">
              {sticker.emoji ?? '🙂'} {sticker.set_name ?? `Stiker ${index + 1}`}
              {sticker.is_animated && <span className="text-xs text-app-hint">(animatsion)</span>}
              <button
                type="button"
                aria-label="O'chirish"
                className="ml-1 text-app-danger"
                disabled={busy}
                onClick={() => void act(() => api(`/api/v1/admin/channel/stickers/${sticker.id}`, { method: 'DELETE' }))}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </Card>
    </>
  )
}
