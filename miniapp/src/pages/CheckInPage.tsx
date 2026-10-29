import { useCallback, useEffect, useRef, useState } from 'react'

import { Icon } from '../components/Icon'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { CheckInResult, ClubEvent, Page } from '../types/api'
import { formatEventDate, formatTime } from '../utils/format'
import { navigate, routeQuery } from '../utils/router'
import { getWebApp, haptic } from '../utils/telegram'

interface LiveAttendance {
  event_id: string
  title: string
  location: string | null
  starts_at: string
  closes_at: string
  checked_in: boolean
}

/**
 * «✅ Davomat»: the quickest way to check in. Opened from the bot with ?scan=1 the QR scanner
 * starts at once; the 6-character code from the screen works too.
 */
export function CheckInPage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<LiveAttendance[]>('/api/v1/attendance/open', { signal }))
  const next = useAsync((signal) => api<Page<ClubEvent>>('/api/v1/events?scope=upcoming&limit=1', { signal }))
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<CheckInResult | null>(null)
  const autoScanned = useRef(false)

  const submit = useCallback(
    async (body: { token?: string; code?: string }) => {
      setBusy(true)
      setError(null)
      try {
        const result = await api<CheckInResult>('/api/v1/attendance/verify', { method: 'POST', body })
        haptic('success')
        setDone(result)
      } catch (err) {
        haptic('error')
        setError(err instanceof ApiError ? err.message : "Davomatni yuborib bo'lmadi. Qayta urinib ko'ring.")
      } finally {
        setBusy(false)
      }
    },
    [api],
  )

  const scan = useCallback(() => {
    const webApp = getWebApp()
    if (!webApp?.showScanQrPopup) {
      setError("Bu qurilmada skaner yo'q. Ekrandagi 6 belgili kodni kiriting.")
      return
    }
    webApp.showScanQrPopup({ text: 'Ekrandagi QR kodni ramkaga to‘g‘rilang' }, (data) => {
      if (!data.includes('att_')) return false
      webApp.closeScanQrPopup?.()
      void submit({ token: data })
      return true
    })
  }, [submit])

  const pending = state.status === 'success' ? state.data.filter((item) => !item.checked_in) : []

  useEffect(() => {
    if (autoScanned.current || pending.length === 0 || routeQuery().get('scan') !== '1') return
    autoScanned.current = true
    scan()
  }, [pending.length, scan])

  if (done) {
    return (
      <Card className="flex flex-col items-center gap-3 py-10 text-center">
        <span className="grid size-16 place-items-center rounded-full bg-green-500/15 text-green-600 dark:text-green-300">
          <Icon name="check-circle" size={40} />
        </span>
        <h1 className="text-xl font-semibold">Davomatingiz qayd etildi!</h1>
        <p className="text-app-hint">«{done.event_title}»</p>
        <p className="text-2xl font-semibold text-app-link">+{done.points} ball</p>
        <Button variant="secondary" onClick={() => navigate('/results')}>
          <Icon name="bar-chart" size={18} />Natijalarim
        </Button>
      </Card>
    )
  }

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />

  if (pending.length === 0) {
    const attended = state.data.find((item) => item.checked_in)
    const upcoming = next.state.status === 'success' ? next.state.data.items[0] : undefined
    return (
      <Card className="flex flex-col items-center gap-3 py-10 text-center">
        <span
          className={`grid size-14 place-items-center rounded-full ${
            attended ? 'bg-green-500/15 text-green-600 dark:text-green-300' : 'bg-app-surface text-app-hint'
          }`}
        >
          <Icon name={attended ? 'check-circle' : 'clock'} size={36} />
        </span>
        <h1 className="text-lg font-semibold">
          {attended ? `Siz «${attended.title}» tadbirida qayd etilgansiz` : "Hozir ochiq davomat yo'q"}
        </h1>
        {!attended && (
          <p className="text-sm text-app-hint">Davomat tadbir boshlanishidan biroz oldin o'zi ochiladi.</p>
        )}
        {upcoming && (
          <button type="button" onClick={() => navigate(`/events/${upcoming.id}`)} className="rounded-xl bg-app-surface px-4 py-3 text-sm">
            <Icon name="calendar" size={14} className="mr-1 inline align-[-2px]" />Keyingi tadbir: <b>«{upcoming.title}»</b>
            <br />
            <span className="text-app-hint">{formatEventDate(upcoming.starts_at)}</span>
          </button>
        )}
        <Button variant="secondary" onClick={reload}>
          <Icon name="refresh" size={18} />Yangilash
        </Button>
      </Card>
    )
  }

  const event = pending[0]
  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-1">
        <p className="text-sm text-app-hint">Davomat ochiq · {formatTime(event.closes_at)} gacha</p>
        <h1 className="text-lg font-semibold">«{event.title}»</h1>
        {event.location && (
          <p className="flex items-center gap-1.5 text-sm text-app-hint">
            <Icon name="map-pin" size={14} className="shrink-0" />
            {event.location}
          </p>
        )}
      </Card>

      <Button loading={busy} onClick={scan} className="py-4 text-lg">
        <Icon name="camera" size={20} />QR kodni skanerlash
      </Button>

      <Card className="flex flex-col gap-2">
        <label htmlFor="code" className="text-sm text-app-hint">
          Yoki ekrandagi 6 belgili kodni kiriting:
        </label>
        <div className="grid grid-cols-[minmax(0,1fr)_7.5rem] gap-2">
          <input
            id="code"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6))}
            onKeyDown={(e) => e.key === 'Enter' && code.length === 6 && void submit({ code })}
            inputMode="text"
            autoCapitalize="characters"
            autoComplete="off"
            placeholder="K7M2QX"
            aria-label="Davomat kodi"
            className="w-full rounded-xl bg-app-surface px-3 py-3 text-center font-mono text-xl tracking-[0.3em] outline-none transition focus:ring-2 focus:ring-brand-400/50"
          />
          <Button disabled={code.length !== 6 || busy} onClick={() => void submit({ code })}>
            Yuborish
          </Button>
        </div>
        <p className="text-xs text-app-hint">Kod har 10 soniyada yangilanadi — eng so'nggisini kiriting.</p>
      </Card>

      {error && (
        <p role="alert" className="text-center text-sm text-app-danger">
          {error}
        </p>
      )}
    </div>
  )
}
