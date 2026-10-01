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
const STATUS_TONE: Record<AttendanceStatus, 'success' | 'warning' | 'danger'> = {
  VERIFIED: 'success',
  SUSPICIOUS: 'warning',
  REVOKED: 'danger',
}
const STATUS_LABELS: Record<AttendanceStatus, string> = {
  VERIFIED: 'Tasdiqlangan',
  SUSPICIOUS: 'Shubhali',
  REVOKED: 'Bekor qilingan',
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
                  Davomatni ochganingizda ekranda QR kod va 6 belgili kod paydo bo'ladi. Ular har 30 soniyada
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
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-right">
                    {canManage && record.status === 'VERIFIED' && (
                      <Button variant="ghost" onClick={() => void changeStatus(record, 'SUSPICIOUS', 'Shubhali deb belgilaysizmi?')}>
                        Shubhali
                      </Button>
                    )}
                    {canManage && record.status !== 'REVOKED' && (
                      <Button
                        variant="ghost"
                        className="text-app-danger"
                        onClick={() => void changeStatus(record, 'REVOKED', 'Davomatni bekor qilasizmi? Ball ham qaytarib olinadi.')}
                      >
                        Bekor qilish
                      </Button>
                    )}
                    {canManage && record.status !== 'VERIFIED' && (
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
      {adding && <ManualAddModal eventId={eventId} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); reload() }} />}
    </>
  )
}

function ManualAddModal({ eventId, onClose, onSaved }: { eventId: string; onClose: () => void; onSaved: () => void }) {
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
        <Field label="A'zoni toping">
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
