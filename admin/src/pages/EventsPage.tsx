import { useState } from 'react'

import { CertificatePicker } from '../components/CertificateDesign'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminEvent, Book, EventStatus, Page, TopEvent } from '../types/api'
import { EVENT_STATUS_LABELS, formatDate, formatDateTime, formatTime, fromLocalInput, toLocalInput } from '../utils/format'
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

function TopEvents() {
  const { api } = useSession()
  const { state } = useAsync((signal) => api<TopEvent[]>('/api/v1/admin/events/top-rated', { signal }))
  if (state.status !== 'success' || state.data.length === 0) return null
  return (
    <Card className="flex flex-col gap-2 p-4">
      <h2 className="font-semibold">⭐ Eng yaxshi o'tgan tadbirlar</h2>
      <p className="text-xs text-app-hint">A'zolar tadbirdan keyin botda bergan baholari bo'yicha (kamida 3 ta baho). Izohlar — tadbirning «Davomat» sahifasida.</p>
      <ol className="flex flex-col gap-1 text-sm">
        {state.data.slice(0, 5).map((item, index) => (
          <li key={item.event_id} className="flex items-center justify-between gap-2">
            <button type="button" className="text-left hover:underline" onClick={() => navigate(`/events/${item.event_id}/attendance`)}>
              {['🥇', '🥈', '🥉'][index] ?? `${index + 1}.`} {item.title} <span className="text-app-hint">· {formatDate(item.starts_at)}</span>
            </button>
            <span className="whitespace-nowrap tabular-nums">
              ⭐ {item.average.toFixed(1)} <span className="text-app-hint">({item.ratings})</span>
            </span>
          </li>
        ))}
      </ol>
    </Card>
  )
}

function when(event: AdminEvent): string {
  if (event.shifts.length === 0) return formatDateTime(event.starts_at)
  return `${formatDate(event.starts_at)} · ${event.shifts.map((shift) => `${shift.position}) ${formatTime(shift.starts_at)}`).join(' ')}`
}

export function EventsPage() {
  const { api, can, admin } = useSession()
  const [editing, setEditing] = useState<AdminEvent | 'new' | null>(null)
  const { state, reload } = useAsync((signal) => api<Page<AdminEvent>>('/api/v1/admin/events?limit=200', { signal }))
  const [error, setError] = useState<string | null>(null)

  async function finish(event: AdminEvent) {
    if (!window.confirm(`«${event.title}» tadbirini hozir yakunlaysizmi? Davomat yopiladi va qatnashchilarga «tadbir tugadi» xabari boradi.`)) return
    setError(null)
    try {
      await api(`/api/v1/admin/events/${event.id}/finish`, { method: 'POST' })
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yakunlab bo'lmadi.")
    }
  }

  return (
    <>
      <PageHeader
        title="Tadbirlar"
        subtitle="Qoralama tadbirlarni a'zolar ko'rmaydi. «E'lon qilingan» tadbir Mini App'da paydo bo'ladi."
        actions={can('EVENT_CREATE') && <Button onClick={() => setEditing('new')}>+ Yangi tadbir</Button>}
      />
      <InlineError message={error} />
      <TopEvents />
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={['Tadbir', 'Vaqti', 'Holat', "Ro'yxat / qatnashdi", 'Baho', '']}>
            {state.data.items.length === 0 && <EmptyRow colSpan={6} text="Tadbirlar hali yaratilmagan" />}
            {state.data.items.map((event) => (
              <tr key={event.id}>
                <td className="px-4 py-2.5">
                  <p className="font-medium">{event.title}</p>
                  <p className="text-xs text-app-hint">
                    {event.location ?? ''} {event.book_title ? `· 📚 ${event.book_title}` : ''}
                  </p>
                </td>
                <td className="px-4 py-2.5">
                  <p className="whitespace-nowrap">{when(event)}</p>
                  {event.shifts.length > 0 && <p className="text-xs text-app-hint">{event.shifts.length} smena</p>}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    <EventStatusBadge status={event.status} />
                    {event.attendance_open && <Badge tone="info">Davomat ochiq</Badge>}
                    {event.pending_requests > 0 && <Badge tone="warning">🙋 {event.pending_requests} so'rov</Badge>}
                  </div>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 tabular-nums">
                  {event.registered_count} / ✓ {event.attended_count}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 tabular-nums">
                  {event.rating != null ? (
                    <span>
                      ⭐ {event.rating.toFixed(1)} <span className="text-app-hint">({event.ratings_count})</span>
                    </span>
                  ) : (
                    <span className="text-app-hint">—</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  {admin?.is_super_admin && event.status === 'PUBLISHED' && new Date(event.starts_at) <= new Date() && (
                    <Button variant="ghost" className="text-app-danger" onClick={() => void finish(event)}>
                      ⏹ Yakunlash
                    </Button>
                  )}
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
          onChanged={reload}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
    </>
  )
}

function EventModal({
  event,
  onClose,
  onSaved,
  onChanged,
}: {
  event: AdminEvent | null
  onClose: () => void
  onSaved: () => void
  onChanged: () => void
}) {
  const { api, can } = useSession()
  const books = useAsync((signal) => api<Page<Book>>('/api/v1/admin/books?limit=200', { signal }))
  const [form, setForm] = useState({
    title: event?.title ?? '',
    description: event?.description ?? '',
    book_id: event?.book_id ?? '',
    location: event?.location ?? '',
    starts_at: toLocalInput(event?.starts_at),
    ends_at: toLocalInput(event?.ends_at),
    // Attendance is set by time only; the date follows the event day automatically.
    attendance_opens_time: event?.attendance_opens_at ? toLocalInput(event.attendance_opens_at).slice(11, 16) : '',
    attendance_closes_time: event?.attendance_closes_at ? toLocalInput(event.attendance_closes_at).slice(11, 16) : '',
    attendance_points: event?.attendance_points_override != null ? String(event.attendance_points_override) : '',
    capacity: event?.capacity ? String(event.capacity) : '',
    status: (event?.status ?? 'DRAFT') as EventStatus,
  })
  const [shifts, setShifts] = useState<{ starts_at: string; ends_at: string }[]>(
    event?.shifts.map((shift) => ({ starts_at: toLocalInput(shift.starts_at), ends_at: toLocalInput(shift.ends_at) })) ?? [],
  )
  const multi = shifts.length > 0
  const shiftsReady = !multi || shifts.every((shift) => shift.starts_at && shift.ends_at)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [field]: e.target.value })
  // P9: one reading contest tied to this event (only for admins who manage contests).
  const [contestOn, setContestOn] = useState(!!event?.campaign)
  const [contest, setContest] = useState({
    name: event?.campaign?.name ?? '',
    points_per_book: event?.campaign ? String(event.campaign.points_per_book) : '10',
    completion_bonus: event?.campaign ? String(event.campaign.completion_bonus) : '0',
    book_ids: event?.campaign?.book_ids ?? ([] as string[]),
  })
  function toggleContest(on: boolean) {
    setContestOn(on)
    if (on && contest.book_ids.length === 0 && form.book_id) setContest((c) => ({ ...c, book_ids: [form.book_id] }))
  }
  function toggleContestBook(id: string) {
    setContest((c) => ({ ...c, book_ids: c.book_ids.includes(id) ? c.book_ids.filter((x) => x !== id) : [...c.book_ids, id] }))
  }

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
    // Combine the chosen time with the event's own day, so attendance is always on the event date.
    const day = form.starts_at.slice(0, 10)
    if (day && form.attendance_opens_time) body.attendance_opens_at = fromLocalInput(`${day}T${form.attendance_opens_time}`)
    if (day && form.attendance_closes_time) body.attendance_closes_at = fromLocalInput(`${day}T${form.attendance_closes_time}`)
    if (multi) {
      const items = shifts.map((shift) => ({ starts_at: fromLocalInput(shift.starts_at), ends_at: fromLocalInput(shift.ends_at) }))
      body.shifts = items
      body.starts_at = items[0].starts_at
      body.ends_at = items[items.length - 1].ends_at
      delete body.attendance_opens_at
      delete body.attendance_closes_at
    } else if (event && event.shifts.length > 0) {
      body.shifts = []
    }
    // P9: attach / update / unlink the event's reading contest (only touched by contest managers).
    if (can('SEASON_MANAGE')) {
      body.campaign =
        contestOn && contest.name.trim().length >= 2 && contest.book_ids.length > 0
          ? {
              name: contest.name.trim(),
              points_per_book: Number(contest.points_per_book || 0),
              completion_bonus: Number(contest.completion_bonus || 0),
              book_ids: contest.book_ids,
            }
          : null
    }
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
          <Button onClick={() => void save()} loading={busy} disabled={!form.title.trim() || (multi ? !shiftsReady : !form.starts_at || !form.ends_at)}>
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
        {!multi && (
          <>
            <Field label="Boshlanishi * (Toshkent vaqti)">
              <Input type="datetime-local" value={form.starts_at} onChange={set('starts_at')} />
            </Field>
            <Field label="Tugashi *">
              <Input type="datetime-local" value={form.ends_at} onChange={set('ends_at')} />
            </Field>
            <Field label="Davomat ochiladi (soat)" hint="Faqat soatni belgilang — sana tadbir kuniga o'zi qo'yiladi. Bo'sh — boshlanishdan 10 daqiqa oldin.">
              <Input type="time" value={form.attendance_opens_time} onChange={set('attendance_opens_time')} />
            </Field>
            <Field label="Davomat yopiladi (soat)" hint="Bo'sh — boshlanganidan 20 daqiqa keyin.">
              <Input type="time" value={form.attendance_closes_time} onChange={set('attendance_closes_time')} />
            </Field>
          </>
        )}
        <div className="flex flex-col gap-2 rounded-lg border border-app-border p-3 sm:col-span-2">
          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={multi}
              onChange={(e) =>
                setShifts(
                  e.target.checked
                    ? [
                        { starts_at: form.starts_at, ends_at: form.ends_at },
                        { starts_at: '', ends_at: '' },
                      ]
                    : [],
                )
              }
            />
            Bir kunda bir necha smena (masalan, 1-smena 10:00, 2-smena 14:00)
          </label>
          {multi && (
            <>
              <p className="text-xs text-app-hint">
                Har bir smenada davomat o'zi ochiladi (boshlanishdan 10 daqiqa oldin, 20 daqiqa keyin yopiladi). A'zo smenasini tanlab ro'yxatdan
                o'tadi, lekin davomat va ball bitta — ikki smenaga kelsa ham bir marta hisoblanadi. Test ham bir marta ishlanadi.
              </p>
              {shifts.map((shift, index) => (
                <div key={index} className="grid items-end gap-2 sm:grid-cols-[auto_1fr_1fr_auto]">
                  <span className="pb-2 text-sm font-medium">{index + 1}-smena</span>
                  <Field label="Boshlanishi">
                    <Input
                      type="datetime-local"
                      value={shift.starts_at}
                      onChange={(e) => setShifts(shifts.map((item, i) => (i === index ? { ...item, starts_at: e.target.value } : item)))}
                    />
                  </Field>
                  <Field label="Tugashi">
                    <Input
                      type="datetime-local"
                      value={shift.ends_at}
                      onChange={(e) => setShifts(shifts.map((item, i) => (i === index ? { ...item, ends_at: e.target.value } : item)))}
                    />
                  </Field>
                  <Button variant="ghost" className="text-app-danger" disabled={shifts.length <= 2} onClick={() => setShifts(shifts.filter((_, i) => i !== index))}>
                    ✕
                  </Button>
                </div>
              ))}
              {shifts.length < 6 && (
                <Button variant="secondary" onClick={() => setShifts([...shifts, { starts_at: '', ends_at: '' }])}>
                  + Smena qo'shish
                </Button>
              )}
            </>
          )}
        </div>
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
      {can('SEASON_MANAGE') && (
        <div className="flex flex-col gap-2 rounded-lg border border-app-border p-3">
          <label className="flex items-center gap-2 text-sm font-medium">
            <input type="checkbox" checked={contestOn} onChange={(e) => toggleContest(e.target.checked)} />
            📖 Shu tadbirga kitob tanlovi biriktirish
          </label>
          <p className="text-xs text-app-hint">
            Bir tadbirga bitta tanlov. Tanlov muddati tadbir sanasiga qarab o'zi qo'yiladi. Keyin «Kitob tanlovlari»
            bo'limidan boshlaysiz, e'lon qilasiz va qatnashchilarni tasdiqlaysiz.
            {event?.campaign && event.campaign.status !== 'DRAFT' && ' Tanlov allaqachon boshlangan.'}
          </p>
          {contestOn && (
            <div className="flex flex-col gap-2">
              <Field label="Tanlov nomi *" hint="Masalan: «O'tkan kunlar» — birga o'qiymiz">
                <Input value={contest.name} onChange={(e) => setContest({ ...contest, name: e.target.value })} maxLength={160} />
              </Field>
              <div className="grid gap-2 sm:grid-cols-2">
                <Field label="Kitob uchun ball">
                  <Input type="number" min={0} max={1000} value={contest.points_per_book} onChange={(e) => setContest({ ...contest, points_per_book: e.target.value })} />
                </Field>
                <Field label="Yakunlash bonusi" hint="Hammasini o'qiganga">
                  <Input type="number" min={0} max={1000} value={contest.completion_bonus} onChange={(e) => setContest({ ...contest, completion_bonus: e.target.value })} />
                </Field>
              </div>
              <Field label="Tanlov kitob(lari) *">
                <div className="max-h-40 overflow-auto rounded border border-app-border p-2">
                  {books.state.status === 'success' &&
                    books.state.data.items.map((book) => (
                      <label key={book.id} className="flex items-center gap-2 py-0.5 text-sm">
                        <input type="checkbox" checked={contest.book_ids.includes(book.id)} onChange={() => toggleContestBook(book.id)} />
                        {book.title} <span className="text-app-hint">— {book.author}</span>
                      </label>
                    ))}
                </div>
              </Field>
            </div>
          )}
        </div>
      )}
      {event ? (
        <CertificatePicker event={event} onChanged={onChanged} />
      ) : (
        <p className="text-xs text-app-hint">🎓 G'oliblar sertifikati dizaynini tadbir saqlangach, shu oynada tanlaysiz.</p>
      )}
      <InlineError message={error} />
    </Modal>
  )
}
