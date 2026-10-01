import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminEvent, Book, EventStatus, Page } from '../types/api'
import { EVENT_STATUS_LABELS, formatDateTime, fromLocalInput, toLocalInput } from '../utils/format'
import { navigate } from '../utils/router'

const STATUS_TONE: Record<EventStatus, 'success' | 'info' | 'neutral' | 'warning'> = {
  PUBLISHED: 'success',
  DRAFT: 'warning',
  COMPLETED: 'info',
  CANCELLED: 'neutral',
}

export function EventStatusBadge({ status }: { status: EventStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{EVENT_STATUS_LABELS[status]}</Badge>
}

export function EventsPage() {
  const { api, can } = useSession()
  const [editing, setEditing] = useState<AdminEvent | 'new' | null>(null)
  const { state, reload } = useAsync((signal) => api<Page<AdminEvent>>('/api/v1/admin/events?limit=200', { signal }))

  return (
    <>
      <PageHeader
        title="Tadbirlar"
        subtitle="Qoralama tadbirlarni a'zolar ko'rmaydi. «E'lon qilingan» tadbir Mini App'da paydo bo'ladi."
        actions={can('EVENT_CREATE') && <Button onClick={() => setEditing('new')}>+ Yangi tadbir</Button>}
      />
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={['Tadbir', 'Vaqti', 'Holat', "Ro'yxat / qatnashdi", '']}>
            {state.data.items.length === 0 && <EmptyRow colSpan={5} text="Tadbirlar hali yaratilmagan" />}
            {state.data.items.map((event) => (
              <tr key={event.id}>
                <td className="px-4 py-2.5">
                  <p className="font-medium">{event.title}</p>
                  <p className="text-xs text-app-hint">
                    {event.location ?? ''} {event.book_title ? `· 📚 ${event.book_title}` : ''}
                  </p>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5">{formatDateTime(event.starts_at)}</td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    <EventStatusBadge status={event.status} />
                    {event.attendance_open && <Badge tone="info">Davomat ochiq</Badge>}
                  </div>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 tabular-nums">
                  {event.registered_count} / ✓ {event.attended_count}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  {can('ATTENDANCE_VIEW') && (
                    <Button variant="ghost" onClick={() => navigate(`/events/${event.id}/attendance`)}>
                      Davomat
                    </Button>
                  )}
                  {can('EVENT_EDIT') && (
                    <Button variant="ghost" onClick={() => setEditing(event)}>
                      Tahrirlash
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {editing && (
        <EventModal
          event={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
    </>
  )
}

function EventModal({ event, onClose, onSaved }: { event: AdminEvent | null; onClose: () => void; onSaved: () => void }) {
  const { api, can } = useSession()
  const books = useAsync((signal) => api<Page<Book>>('/api/v1/admin/books?limit=200', { signal }))
  const [form, setForm] = useState({
    title: event?.title ?? '',
    description: event?.description ?? '',
    book_id: event?.book_id ?? '',
    location: event?.location ?? '',
    starts_at: toLocalInput(event?.starts_at),
    ends_at: toLocalInput(event?.ends_at),
    attendance_opens_at: toLocalInput(event?.attendance_opens_at),
    attendance_closes_at: toLocalInput(event?.attendance_closes_at),
    attendance_points: event?.attendance_points_override != null ? String(event.attendance_points_override) : '',
    capacity: event?.capacity ? String(event.capacity) : '',
    status: (event?.status ?? 'DRAFT') as EventStatus,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [field]: e.target.value })

  async function save() {
    setBusy(true)
    setError(null)
    const body: Record<string, unknown> = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      book_id: form.book_id || null,
      location: form.location.trim() || null,
      starts_at: fromLocalInput(form.starts_at),
      ends_at: fromLocalInput(form.ends_at),
      attendance_points: form.attendance_points === '' ? null : Number(form.attendance_points),
      capacity: form.capacity === '' ? null : Number(form.capacity),
      status: form.status,
    }
    if (form.attendance_opens_at) body.attendance_opens_at = fromLocalInput(form.attendance_opens_at)
    if (form.attendance_closes_at) body.attendance_closes_at = fromLocalInput(form.attendance_closes_at)
    try {
      await api(event ? `/api/v1/admin/events/${event.id}` : '/api/v1/admin/events', {
        method: event ? 'PATCH' : 'POST',
        body,
      })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!event || !window.confirm("Tadbirni o'chirasizmi?")) return
    try {
      await api(`/api/v1/admin/events/${event.id}`, { method: 'DELETE' })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "O'chirib bo'lmadi.")
    }
  }

  const statuses: EventStatus[] = event ? ['DRAFT', 'PUBLISHED', 'COMPLETED', 'CANCELLED'] : ['DRAFT', 'PUBLISHED']
  return (
    <Modal
      title={event ? 'Tadbirni tahrirlash' : 'Yangi tadbir'}
      onClose={onClose}
      wide
      footer={
        <>
          {event && can('EVENT_DELETE') && (
            <Button variant="ghost" className="mr-auto text-app-danger" onClick={() => void remove()}>
              O'chirish
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button onClick={() => void save()} loading={busy} disabled={!form.title.trim() || !form.starts_at || !form.ends_at}>
            Saqlash
          </Button>
        </>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Tadbir nomi *">
          <Input value={form.title} onChange={set('title')} maxLength={255} />
        </Field>
        <Field label="Joyi">
          <Input value={form.location} onChange={set('location')} maxLength={255} placeholder="Masalan: Kutubxona, 2-qavat" />
        </Field>
        <Field label="Boshlanishi * (Toshkent vaqti)">
          <Input type="datetime-local" value={form.starts_at} onChange={set('starts_at')} />
        </Field>
        <Field label="Tugashi *">
          <Input type="datetime-local" value={form.ends_at} onChange={set('ends_at')} />
        </Field>
        <Field label="Davomat ochiladi" hint="Bo'sh qoldirilsa: boshlanishdan 10 daqiqa oldin">
          <Input type="datetime-local" value={form.attendance_opens_at} onChange={set('attendance_opens_at')} />
        </Field>
        <Field label="Davomat yopiladi" hint="Bo'sh qoldirilsa: boshlanganidan 20 daqiqa keyin">
          <Input type="datetime-local" value={form.attendance_closes_at} onChange={set('attendance_closes_at')} />
        </Field>
        <Field label="Kitob">
          <Select value={form.book_id} onChange={set('book_id')}>
            <option value="">— Tanlanmagan —</option>
            {books.state.status === 'success' &&
              books.state.data.items.map((book) => (
                <option key={book.id} value={book.id}>
                  {book.title}
                </option>
              ))}
          </Select>
        </Field>
        <Field label="Holat">
          <Select value={form.status} onChange={set('status')}>
            {statuses.map((value) => (
              <option key={value} value={value}>
                {EVENT_STATUS_LABELS[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Qatnashuv bali" hint="Bo'sh qoldirilsa — sozlamalardagi qiymat">
          <Input type="number" min={0} max={1000} value={form.attendance_points} onChange={set('attendance_points')} />
        </Field>
        <Field label="O'rinlar soni" hint="Bo'sh — cheklanmagan">
          <Input type="number" min={1} value={form.capacity} onChange={set('capacity')} />
        </Field>
      </div>
      <Field label="Tavsif">
        <Textarea value={form.description} onChange={set('description')} maxLength={5000} />
      </Field>
      <InlineError message={error} />
    </Modal>
  )
}
