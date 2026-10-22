import { useEffect, useRef, useState } from 'react'

import { PremiumEmoji } from '../components/PremiumEmoji'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { ChannelOverview, ChannelPost, ChannelPostKind, Faculty, NotificationSummary } from '../types/api'
import { formatDateTime, fromLocalInput } from '../utils/format'
import { navigate } from '../utils/router'

const MAX_LENGTH = 3500

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

const BOT = 'bot'
const ADMINS = 'admins'

/** Telegram HTML (already escaped by the server) shown safely: only simple formatting tags stay. */
function telegramHtml(text: string): string {
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped
    .replace(/&amp;(amp|lt|gt|quot|#39);/g, '&$1;')
    .replace(/&lt;(\/?)(b|i|u|s|code|pre|blockquote)&gt;/g, '<$1$2>')
}

function plain(text: string): string {
  const element = document.createElement('div')
  element.innerHTML = text.replace(/<br\s*\/?>/g, '\n')
  return element.textContent ?? ''
}

type Preview = { text: string; buttons: { text: string; url: string; kind: string }[]; recipients: number }

/** «📢 Xabarlar»: a'zolarga (bot) va kanal(lar)ga — hammasi bitta joydan. «Qayerga yuborish»ni belgilaysiz,
 * matnni bir marta yozasiz, kerakli manzillarga birdek ketadi. Qo'shimcha kanallar Sozlamalar → 📣 Telegram
 * kanalda qo'shiladi va shu yerda ro'yxatda chiqadi. */
export function MessagingPage() {
  const { api, can } = useSession()
  const channel = useAsync((signal) => api<ChannelOverview>('/api/v1/admin/channel', { signal }))
  const summary = useAsync((signal) => api<NotificationSummary>('/api/v1/admin/notifications/summary', { signal }))
  const faculties = useAsync((signal) => api<Faculty[]>('/api/v1/admin/faculties', { signal }))

  const overview = channel.state.status === 'success' ? channel.state.data : null
  const targets = overview?.targets ?? []

  // Which destinations this message goes to: the bot (members) and/or one or more channels.
  const [dest, setDest] = useState<Set<string>>(() => new Set([BOT]))
  const toggle = (key: string) => setDest((old) => {
    const next = new Set(old)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    return next
  })
  const toBot = dest.has(BOT)
  const toAdmins = dest.has(ADMINS)
  const toChannels = targets.filter((t) => dest.has(t.chat_id))

  const [form, setForm] = useState({
    message: '',
    faculty_id: '',
    course: '',
    group_name: '',
    with_app_button: true,
    buttons: '',
    with_channel_button: true,
    scheduled_at: '',
  })
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [field]: e.target.value })
  const [photo, setPhoto] = useState<File | null>(null)
  const [stickerId, setStickerId] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [recipients, setRecipients] = useState<number | null>(null)
  const [adminCount, setAdminCount] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const audience = {
    faculty_id: form.faculty_id || null,
    course: form.course ? Number(form.course) : null,
    group_name: form.group_name.trim() || null,
  }
  const audienceKey = JSON.stringify(audience)

  // Live recipient count for the chosen audience (only while the bot is a destination).
  useEffect(() => {
    if (!toBot) {
      setRecipients(null)
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api<{ recipients: number }>('/api/v1/admin/notifications/broadcast', {
        method: 'POST',
        body: { message: 'preview', ...audience, dry_run: true },
        signal: controller.signal,
      })
        .then((result) => setRecipients(result.recipients))
        .catch(() => setRecipients(null))
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [audienceKey, api, toBot])

  // Live count of administrators (only while «Adminlarga» is a destination).
  useEffect(() => {
    if (!toAdmins) {
      setAdminCount(null)
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api<{ recipients: number }>('/api/v1/admin/notifications/broadcast', {
        method: 'POST',
        body: { message: 'preview', to_admins: true, dry_run: true },
        signal: controller.signal,
      })
        .then((result) => setAdminCount(result.recipients))
        .catch(() => setAdminCount(null))
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [api, toAdmins])

  function resetMessage() {
    setForm({ ...form, message: '', buttons: '', scheduled_at: '' })
    setPhoto(null)
    setStickerId('')
    setPreview(null)
  }

  const botBody = () => ({
    message: form.message.trim(),
    ...audience,
    with_app_button: form.with_app_button,
    buttons: form.buttons.trim() || null,
    scheduled_at: fromLocalInput(form.scheduled_at),
  })

  // «Adminlarga»: the same message to every administrator; the audience filters do not apply.
  const adminBody = () => ({
    message: form.message.trim(),
    with_app_button: form.with_app_button,
    buttons: form.buttons.trim() || null,
    scheduled_at: fromLocalInput(form.scheduled_at),
    to_admins: true,
  })

  async function showPreview() {
    setBusy(true)
    setError(null)
    try {
      setPreview(await api('/api/v1/admin/notifications/broadcast/preview', { method: 'POST', body: botBody() }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ko'rsatib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function sendToMe() {
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      await api('/api/v1/admin/notifications/broadcast', { method: 'POST', body: { ...botBody(), test: true } })
      setDone("✓ Sinov xabari sizga yuborildi — botda qanday ko'rinishini tekshiring.")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  function channelForm(targetChatId: string): FormData {
    const data = new FormData()
    data.append('text', form.message)
    if (photo) data.append('photo', photo)
    if (stickerId) data.append('sticker_id', stickerId)
    data.append('with_button', String(form.with_channel_button))
    const when = fromLocalInput(form.scheduled_at)
    if (when) data.append('scheduled_at', when)
    data.append('target_chat_id', targetChatId)
    return data
  }

  async function send() {
    if (!toBot && !toAdmins && toChannels.length === 0) {
      setError('Kamida bitta manzil tanlang: bot, adminlar yoki kanal.')
      return
    }
    const where = [
      toBot ? `📱 bot (${recipients ?? '?'} a'zo)` : null,
      toAdmins ? `👮 adminlar (${adminCount ?? '?'})` : null,
      ...toChannels.map((t) => `📣 ${t.title}`),
    ]
      .filter(Boolean)
      .join(', ')
    const when = form.scheduled_at ? ` ${formatDateTime(fromLocalInput(form.scheduled_at))} da` : ''
    if (!window.confirm(`Xabar ${where} ga${when} yuboriladi. Davom etasizmi?`)) return
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      const sent: string[] = []
      if (toBot) {
        const result = await api<{ recipients: number }>('/api/v1/admin/notifications/broadcast', { method: 'POST', body: botBody() })
        sent.push(`📱 bot — ${result.recipients} a'zo`)
      }
      if (toAdmins) {
        const result = await api<{ recipients: number }>('/api/v1/admin/notifications/broadcast', { method: 'POST', body: adminBody() })
        sent.push(`👮 adminlar — ${result.recipients}`)
      }
      for (const target of toChannels) {
        await api('/api/v1/admin/channel/posts', { method: 'POST', body: channelForm(target.chat_id) })
        sent.push(`📣 ${target.title}`)
      }
      setDone(
        (form.scheduled_at ? '✓ Rejalashtirildi: ' : '✓ Yuborildi: ') +
          sent.join(' · ') +
          ((toBot || toAdmins) && !form.scheduled_at ? '. Bir necha daqiqada yetkaziladi (tungi tinchlik vaqtida — ertalab).' : '.'),
      )
      resetMessage()
      summary.reload()
      channel.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function act(work: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await work()
      channel.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bajarib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null)
  const hasText = form.message.trim().length >= 1
  const canSendBot = hasText && !!recipients && !!preview
  const canSendAdmins = hasText && !!preview
  const canSendChannel = hasText || !!photo
  const canSend =
    !busy &&
    (toBot || toAdmins || toChannels.length > 0) &&
    (!toBot || canSendBot) &&
    (!toAdmins || canSendAdmins) &&
    (toChannels.length === 0 || canSendChannel)

  if (channel.state.status === 'loading' || summary.state.status === 'loading') return <LoadingState />
  if (channel.state.status === 'error') return <ErrorState message={channel.state.error.message} onRetry={channel.reload} />

  return (
    <>
      <PageHeader
        title="📢 Xabarlar"
        subtitle="A'zolarga (bot), adminlarga va Telegram kanal(lar)ga xabar — hammasi bitta joydan. «Qayerga yuborish»ni belgilang, matnni bir marta yozing. Eslatmalar (tadbir, test, kitob, kun iqtibosi) avtomatik yuboriladi."
      />

      {summary.state.status === 'success' && (!summary.state.data.bot_configured || !summary.state.data.worker_enabled) && (
        <Card className="border-amber-400 p-4 text-sm">
          ⚠️ {!summary.state.data.bot_configured ? "Bot sozlanmagan (BOT_TOKEN yo'q) — xabarlar yuborilmaydi." : ''}{' '}
          {!summary.state.data.worker_enabled ? "Bu serverda fon ishchisi o'chirilgan — xabarlarni alohida ishchi jarayon yuboradi." : ''}
        </Card>
      )}

      <Card className="flex flex-col gap-3 p-4">
        <h2 className="font-semibold">Yangi xabar</h2>

        <Field label="Qayerga yuborish *" hint="Bir nechtasini birdek tanlash mumkin. Qo'shimcha kanallar: Sozlamalar → 📣 Telegram kanal.">
          <div className="flex flex-wrap gap-2">
            <label className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${toBot ? 'border-app-button bg-app-button/10' : 'border-app-border'}`}>
              <input type="checkbox" className="size-4" checked={toBot} onChange={() => toggle(BOT)} />
              📱 Bot — a'zolarga
            </label>
            <label className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${toAdmins ? 'border-app-button bg-app-button/10' : 'border-app-border'}`}>
              <input type="checkbox" className="size-4" checked={toAdmins} onChange={() => toggle(ADMINS)} />
              👮 Adminlarga
              {toAdmins && <span className="text-xs text-app-hint">({adminCount ?? '…'})</span>}
            </label>
            {targets.map((target) => {
              const on = dest.has(target.chat_id)
              return (
                <label key={target.chat_id} className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${on ? 'border-app-button bg-app-button/10' : 'border-app-border'}`}>
                  <input type="checkbox" className="size-4" checked={on} onChange={() => toggle(target.chat_id)} />
                  📣 {target.title}
                  {target.primary && <span className="text-xs text-app-hint">(asosiy)</span>}
                </label>
              )
            })}
            {targets.length === 0 && <span className="text-sm text-app-hint">Kanal kiritilmagan — Sozlamalar → 📣 Telegram kanal.</span>}
          </div>
        </Field>

        <Field label="Xabar matni *" hint={`${form.message.length}/${MAX_LENGTH} belgi.`}>
          <Textarea
            value={form.message}
            onChange={(e) => {
              setForm({ ...form, message: e.target.value })
              setPreview(null)
            }}
            maxLength={MAX_LENGTH}
            rows={6}
            placeholder="Masalan: Ertaga soat 15:00 da kutubxonada «O'tkan kunlar» muhokamasi bo'ladi."
          />
        </Field>

        {toBot && (
          <div className="flex flex-col gap-3 rounded-xl border border-app-border p-3">
            <p className="text-sm font-medium">📱 Bot — a'zolarga</p>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Fakultet">
                <Select value={form.faculty_id} onChange={set('faculty_id')}>
                  <option value="">Hammasi</option>
                  {faculties.state.status === 'success' &&
                    faculties.state.data.map((faculty) => (
                      <option key={faculty.id} value={faculty.id}>
                        {faculty.name}
                      </option>
                    ))}
                </Select>
              </Field>
              <Field label="Kurs">
                <Select value={form.course} onChange={set('course')}>
                  <option value="">Hammasi</option>
                  {[1, 2, 3, 4, 5, 6].map((course) => (
                    <option key={course} value={course}>
                      {course}-kurs
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Guruh">
                <Input value={form.group_name} onChange={set('group_name')} placeholder="Hammasi" maxLength={32} />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.with_app_button} onChange={(e) => setForm({ ...form, with_app_button: e.target.checked })} />
              Xabar ostiga «📱 Ilovada ochish» tugmasini qo'shish
            </label>
            <Field label="Qo'shimcha tugmalar (ixtiyoriy)" hint="Har bir qatorda bitta tugma: «Matn | https://havola».">
              <Textarea
                value={form.buttons}
                onChange={(e) => {
                  setForm({ ...form, buttons: e.target.value })
                  setPreview(null)
                }}
                rows={2}
                maxLength={2000}
                placeholder={'Test | https://kitob.uz\nKanalimiz | https://t.me/FJSTIMutolaaxona'}
              />
            </Field>
          </div>
        )}

        {toChannels.length > 0 && (
          <div className="flex flex-col gap-3 rounded-xl border border-app-border p-3">
            <p className="text-sm font-medium">📣 Kanal(lar): {toChannels.map((t) => t.title).join(', ')}</p>
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
              <Field label="Stiker (ixtiyoriy)" hint={overview?.stickers.length ? undefined : "Botda /stiker buyrug'i bilan qo'shing"}>
                <Select value={stickerId} onChange={(e) => setStickerId(e.target.value)} disabled={!overview?.stickers.length}>
                  <option value="">— stikersiz —</option>
                  {overview?.stickers.map((sticker, index) => (
                    <option key={sticker.id} value={sticker.id}>
                      {sticker.emoji ?? '🙂'} {sticker.set_name ?? `Stiker ${index + 1}`}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.with_channel_button} onChange={(e) => setForm({ ...form, with_channel_button: e.target.checked })} />
              Post ostiga «📲 Botga qo'shilish» tugmasini qo'shish
            </label>
          </div>
        )}

        <Field label="Yuborish vaqti (ixtiyoriy, Toshkent vaqti)" hint="Bo'sh — darhol. Tungi tinchlik vaqtidagi bot xabarlari ertalab boradi.">
          <Input type="datetime-local" value={form.scheduled_at} onChange={set('scheduled_at')} />
        </Field>

        {preview && toBot && (
          <div className="rounded-xl bg-app-surface p-3">
            <p className="mb-2 text-xs text-app-hint">👀 A'zolar shunday ko'radi ({preview.recipients} nafar):</p>
            <div className="max-w-md rounded-2xl rounded-bl-sm bg-app-bg p-3 text-sm shadow-sm">
              <p className="whitespace-pre-line" dangerouslySetInnerHTML={{ __html: telegramHtml(preview.text) }} />
            </div>
            {preview.buttons.length > 0 && (
              <div className="mt-1 flex max-w-md flex-col gap-1">
                {preview.buttons.map((button, index) => (
                  <span key={index} className="rounded-lg bg-app-bg/80 py-1.5 text-center text-sm text-app-link shadow-sm" title={button.url}>
                    {button.text} {button.kind === 'url' ? '↗' : ''}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
        <InlineError message={error} />
        {done && <p className="text-sm text-emerald-600">{done}</p>}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-app-hint">
            {toBot ? (
              <>
                Botda qabul qiluvchilar: <span className="font-semibold text-app-text">{recipients ?? '…'}</span> nafar
              </>
            ) : (
              'Bot tanlanmagan'
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            {toBot && (
              <>
                <Button variant="secondary" disabled={busy || !hasText} onClick={() => void showPreview()}>
                  👀 Ko'rib chiqish
                </Button>
                <Button variant="secondary" disabled={busy || !hasText} onClick={() => void sendToMe()}>
                  🧪 O'zimga sinov
                </Button>
              </>
            )}
            <Button loading={busy} disabled={!canSend} onClick={() => void send()} title={toBot && !preview ? "Avval «Ko'rib chiqish»ni bosing" : undefined}>
              {form.scheduled_at ? '⏰ Rejalashtirish' : '📢 Yuborish'}
            </Button>
          </div>
        </div>
      </Card>

      {overview && (
        <Card className="flex flex-col gap-2 p-4 text-sm">
          <p>
            Asosiy kanal:{' '}
            {overview.link ? (
              <a className="text-app-link underline" href={overview.link} target="_blank" rel="noreferrer">
                {overview.chat_id}
              </a>
            ) : (
              <b>{overview.chat_id ?? 'kiritilmagan'}</b>
            )}{' '}
            · {overview.enabled ? <Badge tone="success">Yoqilgan</Badge> : <Badge tone="warning">O'chiq</Badge>} · navbatda: {overview.pending} · oxirgi post:{' '}
            {overview.last_sent_at ? formatDateTime(overview.last_sent_at) : '—'}
            <Button variant="secondary" className="ml-2" disabled={busy || !overview.chat_id} onClick={() => void act(() => api('/api/v1/admin/channel/test', { method: 'POST' }))}>
              🧪 Sinov posti
            </Button>
          </p>
          {!overview.enabled && (
            <p className="text-app-hint">
              Yoqish: 1) Telegram'da kanal → Administratorlar → botni qo'shing va «Xabar joylash» huquqini bering. 2){' '}
              <button type="button" className="text-app-link underline" onClick={() => navigate('/settings')}>
                Sozlamalar → 📣 Telegram kanal
              </button>{' '}
              → «Bot klub kanaliga post joylaydi» ni yoqing. Qo'shimcha kanallarni ham shu yerda qo'shasiz.
            </p>
          )}
          {overview.last_error && <p className="text-app-danger">⚠️ Oxirgi xato: {overview.last_error}. Bot kanalga admin qilinganini tekshiring.</p>}
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="border-b border-app-border px-4 py-3 font-semibold">So'nggi kanal postlari</h2>
          <Table head={['Turi', 'Matn', 'Holat', '']}>
            {(!overview || overview.posts.length === 0) && <EmptyRow colSpan={4} text="Hali post yo'q" />}
            {overview?.posts.map((post: ChannelPost) => (
              <tr key={post.id} className={post.status === 'CANCELLED' ? 'text-app-hint' : ''}>
                <td className="whitespace-nowrap px-4 py-2 text-sm">{KINDS[post.kind]}</td>
                <td className="max-w-xs px-4 py-2 text-sm">
                  {editing?.id === post.id ? (
                    <div className="flex flex-col gap-2">
                      <textarea
                        className="min-h-24 w-full rounded-lg border border-app-border bg-app-surface p-2 text-sm"
                        value={editing.text}
                        maxLength={4000}
                        onChange={(event) => setEditing({ id: post.id, text: event.target.value })}
                      />
                      <div className="flex gap-2">
                        <Button
                          loading={busy}
                          disabled={!editing.text.trim()}
                          onClick={() =>
                            void act(async () => {
                              await api(`/api/v1/admin/channel/posts/${post.id}/text`, { method: 'PUT', body: { text: editing.text } })
                              setEditing(null)
                            })
                          }
                        >
                          Saqlash va joylash
                        </Button>
                        <Button variant="ghost" onClick={() => setEditing(null)}>
                          Bekor
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <p className="line-clamp-3 whitespace-pre-line">{plain(post.text) || '🖼 (rasm)'}</p>
                  )}
                  {post.in_review && <p className="text-xs font-medium text-app-link">👀 Adminlar tekshiruvida</p>}
                  <p className="text-xs text-app-hint">{formatDateTime(post.sent_at ?? post.scheduled_at)}</p>
                  {post.last_error && post.status !== 'SENT' && <p className="text-xs text-app-danger">{post.last_error}</p>}
                </td>
                <td className="px-4 py-2">
                  <Badge tone={STATUS[post.status].tone}>{STATUS[post.status].label}</Badge>
                </td>
                <td className="px-4 py-2 text-right">
                  {post.status === 'PENDING' && (
                    <div className="flex flex-col items-end gap-1">
                      <Button variant="secondary" disabled={busy} onClick={() => void act(() => api(`/api/v1/admin/channel/posts/${post.id}/publish-now`, { method: 'POST' }))}>
                        ▶️ Hozir joylash
                      </Button>
                      {editing?.id !== post.id && (
                        <Button variant="ghost" disabled={busy} onClick={() => setEditing({ id: post.id, text: post.plain_text })}>
                          ✏️ Tahrirlash
                        </Button>
                      )}
                      <Button variant="ghost" className="text-app-danger" disabled={busy} onClick={() => void act(() => api(`/api/v1/admin/channel/posts/${post.id}/cancel`, { method: 'POST' }))}>
                        Bekor qilish
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        </Card>

        <Card className="flex flex-col gap-2 p-4">
          <h2 className="font-semibold">So'nggi bot e'lonlari</h2>
          {summary.state.status === 'success' && summary.state.data.recent_broadcasts.length === 0 && (
            <p className="text-sm text-app-hint">Hali e'lon yuborilmagan.</p>
          )}
          {summary.state.status === 'success' &&
            summary.state.data.recent_broadcasts.map((item, index) => (
              <div key={index} className="border-t border-app-border pt-2 text-sm first:border-0 first:pt-0">
                <p className="line-clamp-3 whitespace-pre-line">{item.message}</p>
                <p className="mt-1 text-xs text-app-hint">
                  {formatDateTime(item.at)} · {item.actor ?? '—'} · {item.recipients} nafar
                  {item.scheduled_at && item.waiting > 0 && ` · ⏰ ${formatDateTime(item.scheduled_at)}`}
                </p>
              </div>
            ))}
          <p className="mt-2 text-xs text-app-hint">A'zolar botdagi ⚙️ Sozlamalarda eslatmalarni o'chirishi mumkin; muhim e'lonlar baribir yetkaziladi.</p>
        </Card>
      </div>

      {overview && (
        <Card className="flex flex-col gap-2 p-4">
          <h2 className="font-semibold">🎨 Stikerlar ({overview.stickers.length})</h2>
          <p className="text-sm text-app-hint">
            Botga <b>/stiker</b> deb yozing va yoqqan stikerlarni yuboring. Bot ularni mos joyda ishlatadi: 🎉 — g'alaba va tabriklardan keyin, 📚 — kitob
            postlaridan keyin, 👋 — yangi a'zolarga.
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
      )}

      {can('SETTINGS_MANAGE') && (
        <div className="mt-2">
          <PremiumEmoji />
        </div>
      )}
    </>
  )
}
