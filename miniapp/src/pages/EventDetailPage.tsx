import { useCallback, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { CheckInResult, ClubEvent } from '../types/api'
import { formatEventDate, formatTime } from '../utils/format'
import { navigate } from '../utils/router'
import { confirmAction, getWebApp, haptic } from '../utils/telegram'
import { EventBadges } from './EventsPage'

function CheckInCard({ event, onDone }: { event: ClubEvent; onDone: (result: CheckInResult) => void }) {
  const { api } = useAuth()
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(body: { token?: string; code?: string }) {
    setBusy(true)
    setError(null)
    try {
      const response = await api<CheckInResult>('/api/v1/attendance/verify', {
        method: 'POST',
        body: { ...body, event_id: event.id },
      })
      haptic('success')
      onDone(response)
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : "Davomatni yuborib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  function scan() {
    const webApp = getWebApp()
    if (!webApp?.showScanQrPopup) {
      setError("Bu qurilmada skaner mavjud emas. Ekrandagi 6 belgili kodni kiriting.")
      return
    }
    webApp.showScanQrPopup({ text: 'Ekrandagi QR kodni skanerlang' }, (data) => {
      if (!data.includes('att_')) return false
      webApp.closeScanQrPopup?.()
      void submit({ token: data })
      return true
    })
  }

  return (
    <Card className="flex flex-col gap-3">
      <div>
        <h2 className="font-semibold">✅ Davomat</h2>
        <p className="text-sm text-app-hint">
          Davomat {formatTime(event.attendance_opens_at)}–{formatTime(event.attendance_closes_at)} oralig'ida ochiq.
          Ekrandagi QR kodni skanerlang yoki kodni kiriting.
        </p>
      </div>
      <Button loading={busy} onClick={scan}>
        📷 QR kodni skanerlash
      </Button>
      <div className="grid grid-cols-[minmax(0,1fr)_7.5rem] gap-2">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6))}
          inputMode="text"
          autoCapitalize="characters"
          placeholder="Kod: ABC123"
          aria-label="Davomat kodi"
          className="w-full rounded-xl bg-app-surface px-3 py-3 text-center font-mono text-lg tracking-[0.25em] outline-none"
        />
        <Button disabled={code.length !== 6 || busy} onClick={() => void submit({ code })}>
          Yuborish
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-center text-sm text-app-danger">
          {error}
        </p>
      )}
    </Card>
  )
}

export function EventDetailPage({ eventId }: { eventId: string }) {
  const { api } = useAuth()
  const { state, reload } = useAsync((signal) => api<ClubEvent>(`/api/v1/events/${eventId}`, { signal }), [eventId])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checkIn, setCheckIn] = useState<CheckInResult | null>(null)
  const goBack = useCallback(() => navigate('/events'), [])
  useBackButton(goBack)

  async function toggleRegistration(event: ClubEvent) {
    if (event.is_registered && !(await confirmAction("Ro'yxatdan chiqasizmi?"))) return
    setBusy(true)
    setError(null)
    try {
      await api(`/api/v1/events/${event.id}/register`, { method: event.is_registered ? 'DELETE' : 'POST' })
      haptic('success')
      reload()
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(false)
    }
  }

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const event = state.data
  const now = Date.now()
  const started = new Date(event.starts_at).getTime() <= now
  const ended = new Date(event.ends_at).getTime() < now
  // Show the check-in card a little before the window; the server decides whether it is really open.
  const checkInVisible =
    event.status === 'PUBLISHED' &&
    !event.my_attendance &&
    new Date(event.attendance_opens_at).getTime() - 30 * 60_000 <= now &&
    new Date(event.attendance_closes_at).getTime() + 60 * 60_000 >= now

  return (
    <>
      <Card className="flex flex-col gap-2">
        <p className="text-sm font-medium text-app-link">{formatEventDate(event.starts_at)}</p>
        <h1 className="text-xl font-semibold">{event.title}</h1>
        <EventBadges event={event} />
        <div className="mt-1 flex flex-col gap-1 text-sm text-app-hint">
          {event.location && <span>📍 {event.location}</span>}
          {event.book_title && (
            <button type="button" className="text-left text-app-link" onClick={() => navigate(`/books/${event.book_id}`)}>
              📚 {event.book_title}
            </button>
          )}
          <span>
            🕒 {formatTime(event.starts_at)}–{formatTime(event.ends_at)}
          </span>
          <span>🏆 Qatnashganlik uchun {event.attendance_points} ball</span>
          <span>
            👥 {event.registered_count} kishi ro'yxatdan o'tgan
            {event.capacity ? ` · ${event.capacity} o'rin` : ''}
          </span>
        </div>
      </Card>

      {checkIn ? (
        <Card className="flex flex-col items-center gap-1 py-6 text-center">
          <span aria-hidden className="text-4xl">
            ✅
          </span>
          <p className="font-semibold">Davomatingiz qayd etildi!</p>
          <p className="text-sm text-app-hint">+{checkIn.points} ball</p>
        </Card>
      ) : (
        event.my_attendance === 'VERIFIED' && (
          <Card className="text-center">
            <Badge tone="success">✅ Siz bu tadbirda qatnashdingiz</Badge>
          </Card>
        )
      )}

      {checkInVisible && (
        <CheckInCard
          event={event}
          onDone={(result) => {
            setCheckIn(result)
            reload()
          }}
        />
      )}

      {event.status === 'PUBLISHED' && !ended && !event.my_attendance && (
        <Card className="flex flex-col gap-2">
          <Button
            variant={event.is_registered ? 'secondary' : 'primary'}
            loading={busy}
            disabled={started && event.is_registered}
            onClick={() => void toggleRegistration(event)}
          >
            {event.is_registered ? "✓ Ro'yxatdasiz — chiqish" : "Qatnashaman (ro'yxatdan o'tish)"}
          </Button>
          <p className="text-center text-xs text-app-hint">
            Ro'yxatdan o'tish — qatnashish niyatingiz. Davomat tadbirda QR kod orqali qayd etiladi.
          </p>
          {error && (
            <p role="alert" className="text-center text-sm text-app-danger">
              {error}
            </p>
          )}
        </Card>
      )}

      {event.description && (
        <Card>
          <SectionTitle>Tadbir haqida</SectionTitle>
          <p className="whitespace-pre-line text-[15px] leading-relaxed">{event.description}</p>
        </Card>
      )}
    </>
  )
}
