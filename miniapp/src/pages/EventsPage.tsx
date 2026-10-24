import { useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Card } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../store/auth'
import type { ClubEvent, Page } from '../types/api'
import { formatEventDate, formatTime } from '../utils/format'
import { useHomeBackButton } from '../hooks/useBackButton'
import { navigate } from '../utils/router'

export function EventBadges({ event }: { event: ClubEvent }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {event.status === 'CANCELLED' && <Badge tone="warning">Bekor qilingan</Badge>}
      {event.my_attendance === 'VERIFIED' &&
        (new Date(event.ends_at).getTime() > Date.now() ? (
          <Badge tone="success">✅ Qatnashyapsiz</Badge>
        ) : (
          <Badge tone="success">✅ Qatnashdingiz</Badge>
        ))}
      {event.my_attendance === 'SUSPICIOUS' && <Badge tone="warning">Tekshirilmoqda</Badge>}
      {!event.my_attendance && event.is_registered && event.status !== 'CANCELLED' && (
        <Badge tone="info">Ro'yxatdasiz</Badge>
      )}
    </div>
  )
}

export function EventCard({ event }: { event: ClubEvent }) {
  return (
    <button type="button" className="text-left" onClick={() => navigate(`/events/${event.id}`)}>
      <Card className="flex flex-col gap-1.5">
        <p className="text-xs font-medium text-app-link">{formatEventDate(event.starts_at)}</p>
        <h2 className="font-semibold">{event.title}</h2>
        {event.shifts.length > 0 && (
          <p className="text-sm text-app-hint">🕒 {event.shifts.map((shift) => `${shift.position}-smena ${formatTime(shift.starts_at)}`).join(' · ')}</p>
        )}
        {event.location && <p className="text-sm text-app-hint">📍 {event.location}</p>}
        {event.book_title && <p className="text-sm text-app-hint">📚 {event.book_title}</p>}
        <div className="flex items-center justify-between gap-2 pt-1">
          <EventBadges event={event} />
          <span className="text-xs text-app-hint">🏆 {event.attendance_points} ball</span>
        </div>
      </Card>
    </button>
  )
}

export function EventsPage() {
  useHomeBackButton()
  const { api } = useAuth()
  const [scope, setScope] = useState<'upcoming' | 'past'>('upcoming')
  const { state, reload } = useAsync(
    (signal) => api<Page<ClubEvent>>(`/api/v1/events?scope=${scope}&limit=50`, { signal }),
    [scope],
  )

  return (
    <>
      <h1 className="px-1 pt-1 text-xl font-semibold">📅 Tadbirlar</h1>
      <div className="grid grid-cols-2 gap-1 rounded-xl bg-app-bg p-1" role="tablist">
        {(['upcoming', 'past'] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={scope === value}
            onClick={() => setScope(value)}
            className={`rounded-lg py-2 text-sm font-medium ${scope === value ? 'bg-app-button text-app-button-text' : 'text-app-hint'}`}
          >
            {value === 'upcoming' ? 'Kelgusi' : "O'tgan"}
          </button>
        ))}
      </div>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.items.length === 0 && (
        <EmptyState icon="📅" title={scope === 'upcoming' ? "Yaqin kunlarda tadbir yo'q" : "O'tgan tadbirlar yo'q"}>
          Yangi tadbir e'lon qilinganda shu yerda ko'rinadi.
        </EmptyState>
      )}
      {state.status === 'success' && state.data.items.map((event) => <EventCard key={event.id} event={event} />)}
    </>
  )
}
