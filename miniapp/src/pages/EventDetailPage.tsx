import { useCallback, useState } from 'react'

import { useFeature } from '../components/FeatureGate'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { CheckInResult, ClubEvent, EventFeedback } from '../types/api'
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

function FeedbackCard({ eventId }: { eventId: string }) {
  const { api } = useAuth()
  const mine = useAsync((signal) => api<EventFeedback | null>(`/api/v1/events/${eventId}/feedback`, { signal }), [eventId])
  const [rating, setRating] = useState<number | null>(null)
  const [comment, setComment] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (mine.state.status !== 'success') return null
  const current = rating ?? mine.state.data?.rating ?? 0
  const text = comment ?? mine.state.data?.comment ?? ''

  async function save(value: number) {
    setSaving(true)
    setError(null)
    try {
      await api(`/api/v1/events/${eventId}/feedback`, { method: 'PUT', body: { rating: value, comment: text } })
      setRating(value)
      setSaved(true)
      haptic('success')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="flex flex-col gap-2">
      <SectionTitle>⭐ Tadbirga baho bering</SectionTitle>
      <div className="flex justify-center gap-1" role="radiogroup" aria-label="Baho">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={current === n}
            aria-label={`${n} baho`}
            disabled={saving}
            onClick={() => void save(n)}
            className={`text-3xl transition-transform active:scale-90 ${n <= current ? '' : 'opacity-30 grayscale'}`}
          >
            ⭐
          </button>
        ))}
      </div>
      {current > 0 && (
        <>
          <textarea
            value={text}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            rows={3}
            placeholder="Fikringiz (ixtiyoriy): nima yoqdi, nimani yaxshilash kerak?"
            className="w-full rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
          />
          <Button variant="secondary" loading={saving} onClick={() => void save(current)}>
            Fikrni yuborish
          </Button>
        </>
      )}
      {saved && <p className="text-center text-sm text-app-hint">✅ Rahmat! Fikringiz klub rahbariyatiga yetkazildi.</p>}
      {error && (
        <p role="alert" className="text-center text-sm text-app-danger">
          {error}
        </p>
      )}
    </Card>
  )
}

export function EventDetailPage({ eventId }: { eventId: string }) {
  const feedbackAccess = useFeature('event_feedback')
  const { api } = useAuth()
  const { state, reload } = useAsync((signal) => api<ClubEvent>(`/api/v1/events/${eventId}`, { signal }), [eventId])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [checkIn, setCheckIn] = useState<CheckInResult | null>(null)
  const goBack = useCallback(() => navigate('/events'), [])
  useBackButton(goBack)

  async function toggleRegistration(event: ClubEvent, shiftId?: string) {
    const leaving = event.is_registered && (!shiftId || shiftId === event.my_shift_id)
    if (leaving && !(await confirmAction("Ro'yxatdan chiqasizmi?"))) return
    setBusy(true)
    setError(null)
    try {
      await api(`/api/v1/events/${event.id}/register`, {
        method: leaving ? 'DELETE' : 'POST',
        body: leaving ? undefined : { shift_id: shiftId ?? null },
      })
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
        <h1 className="font-serif text-2xl font-bold leading-tight">{event.title}</h1>
        <EventBadges event={event} />
        <div className="mt-1 flex flex-col gap-1 text-sm text-app-hint">
          {event.location && <span>📍 {event.location}</span>}
          {event.book_title && (
            <button type="button" className="text-left text-app-link" onClick={() => navigate(`/books/${event.book_id}`)}>
              📚 {event.book_title}
            </button>
          )}
          {event.shifts.length > 0 ? (
            event.shifts.map((shift) => (
              <span key={shift.id}>
                🕒 {shift.position}-smena: {formatTime(shift.starts_at)}–{formatTime(shift.ends_at)} · {shift.registered_count} kishi
                {shift.id === event.my_shift_id && event.is_registered ? ' · ✅ sizniki' : ''}
              </span>
            ))
          ) : (
            <span>
              🕒 {formatTime(event.starts_at)}–{formatTime(event.ends_at)}
            </span>
          )}
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
            <Badge tone="success">{ended ? '✅ Siz bu tadbirda qatnashdingiz' : '✅ Siz tadbirda qatnashyapsiz'}</Badge>
          </Card>
        )
      )}

      {ended && event.my_attendance === 'VERIFIED' && feedbackAccess === 'on' && <FeedbackCard eventId={event.id} />}

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
          {event.shifts.length > 0 ? (
            <>
              <p className="text-sm font-medium">{event.is_registered ? 'Smenangiz (boshqasini tanlasangiz, o\'tkazamiz):' : 'Qaysi smenada kelasiz?'}</p>
              {event.shifts
                .filter((shift) => new Date(shift.ends_at).getTime() > now)
                .map((shift) => {
                  const mine = event.is_registered && shift.id === event.my_shift_id
                  return (
                    <Button
                      key={shift.id}
                      variant={mine ? 'secondary' : 'primary'}
                      loading={busy}
                      disabled={mine && started}
                      onClick={() => void toggleRegistration(event, shift.id)}
                    >
                      {mine ? `✓ ${shift.position}-smena — chiqish` : `${shift.position}-smena · ${formatTime(shift.starts_at)}`}
                    </Button>
                  )
                })}
            </>
          ) : (
            <Button
              variant={event.is_registered ? 'secondary' : 'primary'}
              loading={busy}
              disabled={started && event.is_registered}
              onClick={() => void toggleRegistration(event)}
            >
              {event.is_registered ? "✓ Ro'yxatdasiz — chiqish" : "Qatnashaman (ro'yxatdan o'tish)"}
            </Button>
          )}
          <p className="text-center text-xs text-app-hint">
            Ro'yxatdan o'tsangiz, joylarni shunga qarab tayyorlaymiz va sizga tadbir oldidan hamda davomat ochilganda eslatma yuboramiz. Davomat
            tadbirda QR kod orqali qayd etiladi.
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
