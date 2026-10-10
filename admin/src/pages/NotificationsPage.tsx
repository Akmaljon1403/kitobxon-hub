import { useEffect, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, Field, InlineError, Input, PageHeader, Select, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Faculty, NotificationSummary } from '../types/api'
import { formatDateTime } from '../utils/format'

const MAX_LENGTH = 3500

function Stat({ label, value, tone = '' }: { label: string; value: number; tone?: string }) {
  return (
    <Card className="p-4">
      <p className="text-sm text-app-hint">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value}</p>
    </Card>
  )
}

/** Telegram HTML of the bot (already escaped by the server) shown safely: only simple formatting tags stay. */
function telegramHtml(text: string): string {
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped
    .replace(/&amp;(amp|lt|gt|quot|#39);/g, '&$1;')
    .replace(/&lt;(\/?)(b|i|u|s|code|pre|blockquote)&gt;/g, '<$1$2>')
}

export function NotificationsPage() {
  const { api } = useSession()
  const summary = useAsync((signal) => api<NotificationSummary>('/api/v1/admin/notifications/summary', { signal }))
  const faculties = useAsync((signal) => api<Faculty[]>('/api/v1/admin/faculties', { signal }))
  const [form, setForm] = useState({ message: '', faculty_id: '', course: '', group_name: '', with_app_button: true, buttons: '' })
  const [preview, setPreview] = useState<{ text: string; buttons: { text: string; url: string; kind: string }[]; recipients: number } | null>(null)
  const [recipients, setRecipients] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const audience = {
    faculty_id: form.faculty_id || null,
    course: form.course ? Number(form.course) : null,
    group_name: form.group_name.trim() || null,
  }
  const audienceKey = JSON.stringify(audience)

  // Live recipient count for the chosen audience.
  useEffect(() => {
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
  }, [audienceKey, api])

  const body = () => ({
    message: form.message.trim(),
    ...audience,
    with_app_button: form.with_app_button,
    buttons: form.buttons.trim() || null,
  })

  async function showPreview() {
    setBusy(true)
    setError(null)
    try {
      setPreview(await api('/api/v1/admin/notifications/broadcast/preview', { method: 'POST', body: body() }))
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
      await api('/api/v1/admin/notifications/broadcast', { method: 'POST', body: { ...body(), test: true } })
      setDone("✓ Sinov xabari sizga yuborildi — botda qanday ko'rinishini tekshiring.")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function send() {
    if (!window.confirm(`Xabar ${recipients ?? ''} nafar a'zoga yuboriladi. Davom etasizmi?`)) return
    setBusy(true)
    setError(null)
    setDone(null)
    try {
      const result = await api<{ recipients: number }>('/api/v1/admin/notifications/broadcast', {
        method: 'POST',
        body: body(),
      })
      setDone(`✓ Xabar ${result.recipients} nafar a'zoga navbatga qo'yildi. Bir necha daqiqada yetkaziladi.`)
      setForm({ ...form, message: '', buttons: '' })
      setPreview(null)
      summary.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Xabarlar"
        subtitle="A'zolarga bot orqali e'lon yuborish. Eslatmalar (tadbir, test, kitob muddati, kun iqtibosi) avtomatik yuboriladi."
      />
      {summary.state.status === 'loading' && <LoadingState />}
      {summary.state.status === 'error' && <ErrorState message={summary.state.error.message} onRetry={summary.reload} />}
      {summary.state.status === 'success' && (
        <>
          {(!summary.state.data.bot_configured || !summary.state.data.worker_enabled) && (
            <Card className="border-amber-400 p-4 text-sm">
              ⚠️ {!summary.state.data.bot_configured ? 'Bot sozlanmagan (BOT_TOKEN yo\'q) — xabarlar yuborilmaydi.' : ''}{' '}
              {!summary.state.data.worker_enabled
                ? 'Bu serverda fon ishchisi o\'chirilgan — xabarlarni alohida ishchi jarayon yuboradi.'
                : ''}
            </Card>
          )}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Navbatda" value={summary.state.data.pending} />
            <Stat label="Yuborildi (24 soat)" value={summary.state.data.sent_24h} tone="text-emerald-600" />
            <Stat label="Yetkazilmadi (24 soat)" value={summary.state.data.failed_24h} tone={summary.state.data.failed_24h ? 'text-app-danger' : ''} />
            <Stat label="O'tkazib yuborildi (24 soat)" value={summary.state.data.skipped_24h} />
          </div>
        </>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card className="flex flex-col gap-3 p-4">
          <h2 className="font-semibold">Yangi e'lon</h2>
          <Field label="Xabar matni *" hint={`${form.message.length}/${MAX_LENGTH} belgi. Boshiga «📢» avtomatik qo'shiladi.`}>
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
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Fakultet">
              <Select value={form.faculty_id} onChange={(e) => setForm({ ...form, faculty_id: e.target.value })}>
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
              <Select value={form.course} onChange={(e) => setForm({ ...form, course: e.target.value })}>
                <option value="">Hammasi</option>
                {[1, 2, 3, 4, 5, 6].map((course) => (
                  <option key={course} value={course}>
                    {course}-kurs
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Guruh">
              <Input value={form.group_name} onChange={(e) => setForm({ ...form, group_name: e.target.value })} placeholder="Hammasi" maxLength={32} />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.with_app_button}
              onChange={(e) => setForm({ ...form, with_app_button: e.target.checked })}
            />
            Xabar ostiga «📱 Ilovada ochish» tugmasini qo'shish
          </label>
          <Field
            label="Qo'shimcha tugmalar (ixtiyoriy)"
            hint="Har bir qatorda bitta tugma: «Matn | https://havola». Masalan: Ro'yxatdan o'tish | https://forms.gle/..."
          >
            <Textarea
              value={form.buttons}
              onChange={(e) => {
                setForm({ ...form, buttons: e.target.value })
                setPreview(null)
              }}
              rows={3}
              maxLength={2000}
              placeholder={'Test | https://kitob.uz\nKanalimiz | https://t.me/FJSTIMutolaaxona'}
            />
          </Field>
          {preview && (
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
              Qabul qiluvchilar: <span className="font-semibold text-app-text">{recipients ?? '…'}</span> nafar faol a'zo
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" disabled={busy || form.message.trim().length < 3} onClick={() => void showPreview()}>
                👀 Ko'rib chiqish
              </Button>
              <Button variant="secondary" disabled={busy || form.message.trim().length < 3} onClick={() => void sendToMe()}>
                🧪 O'zimga sinov
              </Button>
              <Button loading={busy} disabled={form.message.trim().length < 3 || !recipients || !preview} onClick={() => void send()} title={preview ? undefined : "Avval «Ko'rib chiqish»ni bosing"}>
                📢 Yuborish
              </Button>
            </div>
          </div>
        </Card>

        <Card className="flex flex-col gap-2 p-4">
          <h2 className="font-semibold">So'nggi e'lonlar</h2>
          {summary.state.status === 'success' && summary.state.data.recent_broadcasts.length === 0 && (
            <p className="text-sm text-app-hint">Hali e'lon yuborilmagan.</p>
          )}
          {summary.state.status === 'success' &&
            summary.state.data.recent_broadcasts.map((item, index) => (
              <div key={index} className="border-t border-app-border pt-2 text-sm first:border-0 first:pt-0">
                <p className="line-clamp-3 whitespace-pre-line">{item.message}</p>
                <p className="mt-1 text-xs text-app-hint">
                  {formatDateTime(item.at)} · {item.actor ?? '—'} · {item.recipients} nafar
                </p>
              </div>
            ))}
          <p className="mt-2 text-xs text-app-hint">
            A'zolar botdagi ⚙️ Sozlamalar bo'limida eslatmalarni o'chirib qo'yishi mumkin; muhim e'lonlar baribir yetkaziladi.
          </p>
        </Card>
      </div>
    </>
  )
}
