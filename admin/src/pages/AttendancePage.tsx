import QRCode from 'qrcode'
import { useCallback, useEffect, useRef, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminEvent, AdminUser, AttendanceOverview, AttendanceRecord, AttendanceStatus, AttendanceToken, Page } from '../types/api'
import { formatDateTime, formatTime } from '../utils/format'
import { navigate } from '../utils/router'

const METHOD_LABELS = { QR: 'QR', CODE: 'Kod', MANUAL: 'Admin' } as const
const STATUS_TONE: Record<AttendanceStatus, 'success' | 'warning' | 'danger' | 'info'> = {
  VERIFIED: 'success',
  SUSPICIOUS: 'warning',
  REVOKED: 'danger',
  PENDING: 'info',
}
const STATUS_LABELS: Record<AttendanceStatus, string> = {
  VERIFIED: 'Tasdiqlangan',
  SUSPICIOUS: 'Shubhali',
  REVOKED: 'Bekor qilingan',
  PENDING: '⏳ Tasdiq kutilmoqda',
}

/** Polls the server for the current rotating token and renders it as a large QR code. */
function QrScreen({ eventId, onClosed }: { eventId: string; onClosed: () => void }) {
  const { api } = useSession()
  const [token, setToken] = useState<AttendanceToken | null>(null)
  const [image, setImage] = useState<string | null>(null)
  const [now, setNow] = useState(Date.now())
  const [error, setError] = useState<string | null>(null)
  const [fullscreen, setFullscreen] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const refresh = useCallback(async () => {
    try {
      const next = await api<AttendanceToken>(`/api/v1/admin/events/${eventId}/attendance/token`)
      setToken(next)
      setError(null)
      setImage(await QRCode.toDataURL(next.qr_payload, { width: 640, margin: 1, errorCorrectionLevel: 'M' }))
      const wait = Math.max(1000, new Date(next.rotates_at).getTime() - Date.now() + 300)
      timer.current = setTimeout(() => void refresh(), wait)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'ATTENDANCE_CLOSED') {
        onClosed()
        return
      }
      setError(err instanceof ApiError ? err.message : 'Aloqa uzildi, qayta urinilmoqda…')
      timer.current = setTimeout(() => void refresh(), 3000)
    }
  }, [api, eventId, onClosed])

  useEffect(() => {
    void refresh()
    const tick = setInterval(() => setNow(Date.now()), 500)
    return () => {
      if (timer.current) clearTimeout(timer.current)
      clearInterval(tick)
    }
  }, [refresh])

  const secondsLeft = token ? Math.max(0, Math.ceil((new Date(token.rotates_at).getTime() - now) / 1000)) : 0
  const content = (
    <div className="flex flex-col items-center gap-4">
      {image ? (
        <img src={image} alt="Davomat QR kodi" className={fullscreen ? 'size-[min(70vh,70vw)]' : 'size-72'} />
      ) : (
        <LoadingState />
      )}
      {token && (
        <>
          <p className={`font-mono font-bold tracking-[0.35em] ${fullscreen ? 'text-6xl' : 'text-4xl'}`}>{token.code}</p>
          <p className="text-sm text-app-hint">
            Kod {secondsLeft} soniyadan keyin yangilanadi · Davomat {formatTime(token.session_closes_at)} gacha
          </p>
        </>
      )}
      <InlineError message={error} />
    </div>
  )

  if (fullscreen) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-white p-6 text-black">
        <p className="text-2xl font-semibold">📷 Telefon kamerasi yoki Mini App orqali skanerlang</p>
        {content}
        <Button variant="secondary" onClick={() => setFullscreen(false)}>
          Kichraytirish
        </Button>
      </div>
    )
  }
  return (
    <Card className="flex flex-col items-center gap-3 p-6">
      {content}
      <Button variant="secondary" onClick={() => setFullscreen(true)}>
        ⛶ Proyektor rejimi (to'liq ekran)
      </Button>
    </Card>
  )
}

export function AttendancePage({ eventId }: { eventId: string }) {
  const { api, can } = useSession()
  const canManage = can('ATTENDANCE_MANAGE')
  const event = useAsync((signal) => api<AdminEvent>(`/api/v1/admin/events/${eventId}`, { signal }), [eventId])
  const { state, reload } = useAsync(
    (signal) => api<AttendanceOverview>(`/api/v1/admin/events/${eventId}/attendance`, { signal }),
    [eventId],
  )
  const [minutes, setMinutes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  // Live list: refresh every 5 seconds while the page is open.
  useEffect(() => {
    const interval = setInterval(reload, 5000)
    return () => clearInterval(interval)
  }, [reload])

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(false)
    }
  }

  async function changeStatus(record: AttendanceRecord, status: AttendanceStatus, question: string) {
    const reason = window.prompt(`${question}\n\nSababini yozing (kamida 5 belgi):`)
    if (!reason) return
    await run(() => api(`/api/v1/admin/attendance/${record.id}`, { method: 'PATCH', body: { status, reason } }))
  }

  async function download() {
    const token = sessionStorage.getItem('kitobxon.admin.token')
    const response = await fetch(`/api/v1/admin/events/${eventId}/attendance.csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) {
      setError("Faylni yuklab bo'lmadi.")
      return
    }
    const blob = await response.blob()
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `davomat_${event.state.status === 'success' ? event.state.data.title : 'tadbir'}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  // Keep showing the last data while the 5-second refresh is loading (no flicker).
  const [overview, setOverview] = useState<AttendanceOverview | null>(null)
  useEffect(() => {
    if (state.status === 'success') setOverview(state.data)
  }, [state])

  return (
    <>
      <PageHeader
        title={event.state.status === 'success' ? event.state.data.title : 'Davomat'}
        subtitle={event.state.status === 'success' ? formatDateTime(event.state.data.starts_at) : undefined}
        actions={
          <>
            <Button variant="secondary" onClick={() => navigate('/events')}>
              ← Tadbirlar
            </Button>
            <Button variant="secondary" onClick={() => void download()}>
              ⬇ Excel (CSV)
            </Button>
          </>
        }
      />
      <InlineError message={error} />
      {overview && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
          <div className="flex flex-col gap-4">
            {overview.is_open ? (
              <>
                {canManage && <QrScreen eventId={eventId} onClosed={reload} />}
                {canManage && (
                  <Button variant="danger" loading={busy} onClick={() => void run(() => api(`/api/v1/admin/events/${eventId}/attendance/close`, { method: 'POST' }))}>
                    Davomatni yopish
                  </Button>
                )}
              </>
            ) : (
              <Card className="flex flex-col gap-3 p-5">
                <h2 className="font-semibold">Davomat yopiq</h2>
                <p className="text-sm text-app-hint">
                  Davomatni ochganingizda ekranda QR kod va 6 belgili kod paydo bo'ladi. Ular har 10 soniyada
                  yangilanadi, shuning uchun suratga olib boshqaga yuborish deyarli foyda bermaydi.
                </p>
                {canManage && (
                  <div className="flex flex-wrap items-end gap-2">
                    <Field label="Necha daqiqa ochiq tursin?" hint="Bo'sh — tadbir sozlamasidagi vaqtgacha">
                      <Input type="number" min={1} max={600} value={minutes} onChange={(e) => setMinutes(e.target.value)} className="w-40" />
                    </Field>
                    <Button
                      loading={busy}
                      onClick={() =>
                        void run(() =>
                          api(`/api/v1/admin/events/${eventId}/attendance/open`, {
                            method: 'POST',
                            body: { minutes: minutes ? Number(minutes) : null },
                          }),
                        )
                      }
                    >
                      ▶ Davomatni ochish
                    </Button>
                  </div>
                )}
              </Card>
            )}
          </div>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-app-border px-4 py-3">
              <p className="font-semibold">
                Qatnashdi: {overview.attended_count}
                <span className="font-normal text-app-hint"> · Ro'yxatdan o'tgan: {overview.registered_count}</span>
              </p>
              {canManage && (
                <Button variant="secondary" onClick={() => setAdding(true)}>
                  + Qo'lda qo'shish
                </Button>
              )}
              {overview.shift && <p className="w-full text-xs text-app-hint">Hozir ochiq: {overview.shift}-smena davomati</p>}
            </div>
            <Table head={["A'zo", 'Vaqt', 'Usul', 'Holat', '']}>
              {overview.records.length === 0 && <EmptyRow colSpan={5} text="Hali hech kim qayd etilmagan" />}
              {overview.records.map((record) => (
                <tr key={record.id}>
                  <td className="px-4 py-2">
                    {record.last_name} {record.first_name}
                    <p className="text-xs text-app-hint">
                      {record.faculty_name ?? ''} {record.group_name ?? ''}
                    </p>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 tabular-nums">{formatTime(record.checked_in_at)}</td>
                  <td className="px-4 py-2">{METHOD_LABELS[record.method]}</td>
                  <td className="px-4 py-2">
                    <Badge tone={STATUS_TONE[record.status]}>{STATUS_LABELS[record.status]}</Badge>
                    {record.status === 'PENDING' && (
                      <p className="mt-1 max-w-56 text-xs text-app-hint">
                        {record.requested_by_name ?? 'Admin'} qo'shdi: {record.note}
                      </p>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-right">
                    {record.status === 'PENDING' && overview.can_approve && (
                      <>
                        <Button variant="ghost" onClick={() => void run(() => api(`/api/v1/admin/attendance/${record.id}/approve`, { method: 'POST' }))}>
                          ✅ Tasdiqlash
                        </Button>
                        <Button
                          variant="ghost"
                          className="text-app-danger"
                          onClick={() => void run(() => api(`/api/v1/admin/attendance/${record.id}/reject`, { method: 'POST', body: {} }))}
                        >
                          Rad etish
                        </Button>
                      </>
                    )}
                    {canManage && record.status === 'VERIFIED' && (
                      <Button variant="ghost" onClick={() => void changeStatus(record, 'SUSPICIOUS', 'Shubhali deb belgilaysizmi?')}>
                        Shubhali
                      </Button>
                    )}
                    {canManage && record.status !== 'REVOKED' && record.status !== 'PENDING' && (
                      <Button
                        variant="ghost"
                        className="text-app-danger"
                        onClick={() => void changeStatus(record, 'REVOKED', 'Davomatni bekor qilasizmi? Ball ham qaytarib olinadi.')}
                      >
                        Bekor qilish
                      </Button>
                    )}
                    {canManage && record.status !== 'VERIFIED' && record.status !== 'PENDING' && (
                      <Button variant="ghost" onClick={() => void changeStatus(record, 'VERIFIED', 'Davomatni tasdiqlaysizmi?')}>
                        Tasdiqlash
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
          </Card>
        </div>
      )}
      {state.status === 'loading' && !overview && <LoadingState />}
      {state.status === 'error' && !overview && <ErrorState message={state.error.message} onRetry={reload} />}
      <FeedbackSummary eventId={eventId} />
      {adding && (
        <ManualAddModal
          eventId={eventId}
          direct={Boolean(overview?.can_approve)}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false)
            reload()
          }}
        />
      )}
    </>
  )
}

function ManualAddModal({ eventId, direct, onClose, onSaved }: { eventId: string; direct: boolean; onClose: () => void; onSaved: () => void }) {
  const { api } = useSession()
  const [search, setSearch] = useState('')
  const [results, setResults] = useState<AdminUser[]>([])
  const [member, setMember] = useState<AdminUser | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (search.trim().length < 2) {
      setResults([])
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api<Page<AdminUser>>(`/api/v1/admin/users?status=ACTIVE&limit=8&search=${encodeURIComponent(search.trim())}`, {
        signal: controller.signal,
      })
        .then((page) => setResults(page.items))
        .catch(() => undefined)
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [search, api])

  async function save() {
    if (!member) return
    setBusy(true)
    setError(null)
    try {
      await api(`/api/v1/admin/events/${eventId}/attendance/manual`, {
        method: 'POST',
        body: { user_id: member.id, note: note.trim() },
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
      title="Davomatga qo'lda qo'shish"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button onClick={() => void save()} loading={busy} disabled={!member || note.trim().length < 5}>
            Qo'shish
          </Button>
        </>
      }
    >
      <p className="text-sm text-app-hint">
        Faqat a'zo tadbirda bo'lgani aniq bo'lsa foydalaning (masalan, telefoni ishlamay qolgan). Amal audit jurnaliga yoziladi.
        {direct
          ? ' Siz bosh administratorsiz — davomat darhol hisoblanadi.'
          : " So'rov bosh administratorga yuboriladi: u tasdiqlagachgina a'zoga ball beriladi."}
      </p>
      {member ? (
        <div className="flex items-center justify-between rounded-lg border border-app-border px-3 py-2 text-sm">
          <span>
            {member.last_name} {member.first_name} · {member.group_name ?? ''}
          </span>
          <Button variant="ghost" onClick={() => setMember(null)}>
            O'zgartirish
          </Button>
        </div>
      ) : (
        <Field label="A'zoni toping" hint="Ism, familiya, guruh yoki telefon raqami bo'yicha">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Ism yoki familiya…" />
          {results.length > 0 && (
            <ul className="mt-1 divide-y divide-app-border rounded-lg border border-app-border">
              {results.map((user) => (
                <li key={user.id}>
                  <button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-app-surface" onClick={() => setMember(user)}>
                    {user.last_name} {user.first_name}
                    <span className="text-app-hint"> · {user.group_name ?? ''}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Field>
      )}
      <Field label="Sabab *">
        <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Masalan: telefoni o'chib qolgan, shaxsan ko'rildi" />
      </Field>
      <InlineError message={error} />
    </Modal>
  )
}


interface Feedback {
  count: number
  average: number | null
  distribution: Record<string, number>
  comments: { rating: number; comment: string; name: string; updated_at: string }[]
}

/** ⭐ What members said after the event (the bot asks them 30 minutes after the end). */
function FeedbackSummary({ eventId }: { eventId: string }) {
  const { api } = useSession()
  const { state } = useAsync((signal) => api<Feedback>(`/api/v1/admin/events/${eventId}/feedback`, { signal }), [eventId])
  if (state.status !== 'success' || state.data.count === 0) return null
  const feedback = state.data
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">⭐ A'zolar bahosi</h2>
        <p className="text-sm text-app-hint">
          <span className="text-2xl font-semibold text-app-text tabular-nums">{feedback.average}</span> / 5 · {feedback.count} ta baho
        </p>
      </div>
      <div className="flex flex-col gap-1">
        {['5', '4', '3', '2', '1'].map((stars) => {
          const count = feedback.distribution[stars] ?? 0
          return (
            <div key={stars} className="flex items-center gap-2 text-sm">
              <span className="w-8 tabular-nums">{stars}⭐</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-app-surface">
                <div className="h-full rounded-full bg-amber-400" style={{ width: `${(count / feedback.count) * 100}%` }} />
              </div>
              <span className="w-6 text-right tabular-nums text-app-hint">{count}</span>
            </div>
          )
        })}
      </div>
      {feedback.comments.length > 0 && (
        <ul className="divide-y divide-app-border text-sm">
          {feedback.comments.map((item, index) => (
            <li key={index} className="py-2">
              <p>{item.comment}</p>
              <p className="text-xs text-app-hint">
                {'⭐'.repeat(item.rating)} · {item.name} · {formatDateTime(item.updated_at)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
