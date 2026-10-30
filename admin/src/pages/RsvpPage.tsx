import { useMemo, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Input, PageHeader, Select, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useSession } from '../store/session'
import type { AdminEvent, EventRegistration, RsvpStatus, RsvpSummary } from '../types/api'
import { formatDateTime } from '../utils/format'
import { navigate } from '../utils/router'

const ANSWER_TONE: Record<RsvpStatus, 'success' | 'danger' | 'neutral'> = {
  REGISTERED: 'success',
  DECLINED: 'danger',
  CANCELLED: 'neutral',
}
const ANSWER_LABELS: Record<RsvpStatus, string> = {
  REGISTERED: 'Qatnashaman',
  DECLINED: 'Bora olmayman',
  CANCELLED: 'Bekor qilgan',
}

/** A headline number with a caption — the «who answered how» summary. */
function StatCard({ value, label, tone }: { value: number; label: string; tone: 'success' | 'danger' | 'muted' }) {
  const color =
    tone === 'success' ? 'text-emerald-600 dark:text-emerald-400' : tone === 'danger' ? 'text-app-danger' : 'text-app-hint'
  return (
    <Card className="flex flex-col gap-1 p-4">
      <p className={`text-3xl font-bold tabular-nums ${color}`}>{value}</p>
      <p className="text-sm text-app-hint">{label}</p>
    </Card>
  )
}

export function RsvpPage({ eventId }: { eventId: string }) {
  const { api, download } = useSession()
  const event = useAsync((signal) => api<AdminEvent>(`/api/v1/admin/events/${eventId}`, { signal }), [eventId])
  const summary = useAsync((signal) => api<RsvpSummary>(`/api/v1/admin/events/${eventId}/rsvp-summary`, { signal }), [eventId])
  const registrations = useAsync(
    (signal) => api<EventRegistration[]>(`/api/v1/admin/events/${eventId}/registrations`, { signal }),
    [eventId],
  )

  const [search, setSearch] = useState('')
  const [faculty, setFaculty] = useState('')
  const [course, setCourse] = useState('')
  const [group, setGroup] = useState('')
  const [answer, setAnswer] = useState<'' | RsvpStatus>('')
  const [error, setError] = useState<string | null>(null)

  const rows = registrations.state.status === 'success' ? registrations.state.data : []

  // The filter dropdowns offer only the values that actually appear among the answers.
  const faculties = useMemo(() => [...new Set(rows.map((r) => r.faculty_name).filter((v): v is string => !!v))].sort(), [rows])
  const courses = useMemo(() => [...new Set(rows.map((r) => r.course).filter((v): v is number => v != null))].sort((a, b) => a - b), [rows])
  const groups = useMemo(() => [...new Set(rows.map((r) => r.group_name).filter((v): v is string => !!v))].sort(), [rows])

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return rows.filter((r) => {
      if (answer && r.status !== answer) return false
      if (faculty && r.faculty_name !== faculty) return false
      if (course && String(r.course) !== course) return false
      if (group && r.group_name !== group) return false
      if (needle && !`${r.last_name} ${r.first_name}`.toLowerCase().includes(needle)) return false
      return true
    })
  }, [rows, search, answer, faculty, course, group])

  async function downloadFile(path: string, prefix: string) {
    setError(null)
    try {
      const blob = await download(path)
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `${prefix}_${event.state.status === 'success' ? event.state.data.title : 'tadbir'}.csv`
      link.click()
      URL.revokeObjectURL(link.href)
    } catch {
      setError("Faylni yuklab bo'lmadi.")
    }
  }
  const downloadCsv = () => downloadFile(`/api/v1/admin/events/${eventId}/registrations.csv`, 'javoblar')
  const downloadAnalytics = () => downloadFile(`/api/v1/admin/events/${eventId}/analytics.csv`, 'tahlil')

  const data = summary.state.status === 'success' ? summary.state.data : null

  return (
    <>
      <PageHeader
        title={event.state.status === 'success' ? event.state.data.title : 'Javoblar'}
        subtitle={event.state.status === 'success' ? `${formatDateTime(event.state.data.starts_at)} · Kim qatnashadi` : undefined}
        actions={
          <>
            <Button variant="secondary" onClick={() => navigate('/events')}>
              ← Tadbirlar
            </Button>
            <Button variant="secondary" onClick={() => navigate(`/events/${eventId}/attendance`)}>
              Davomat
            </Button>
            <Button variant="secondary" onClick={() => void downloadCsv()} disabled={rows.length === 0}>
              ⬇ Javoblar (CSV)
            </Button>
            <Button variant="secondary" onClick={() => void downloadAnalytics()}>
              📊 Tahlil (CSV)
            </Button>
          </>
        }
      />
      {error && <p className="mb-3 text-sm text-app-danger">{error}</p>}

      {summary.state.status === 'loading' && <LoadingState />}
      {summary.state.status === 'error' && <ErrorState message={summary.state.error.message} onRetry={summary.reload} />}
      {data && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatCard value={data.coming} label="✅ Qatnashaman" tone="success" />
            <StatCard value={data.declined} label="✖️ Bu safar bora olmayman" tone="danger" />
            <StatCard value={data.no_answer} label="Javob bermagan" tone="muted" />
          </div>
          <p className="text-xs text-app-hint">
            Jami faol a'zo: {data.active_members}. A'zo tadbir tugaguncha javobini o'zgartirishi mumkin — faqat oxirgi javob hisobga olinadi.
          </p>

          {data.shifts.length > 0 && (
            <Card className="p-4">
              <h2 className="mb-2 font-semibold">Smenalar bo'yicha</h2>
              <Table head={['Smena', '✅ Qatnashaman', '✖️ Bora olmayman']}>
                {data.shifts.map((shift) => (
                  <tr key={shift.shift_id}>
                    <td className="px-4 py-2">{shift.position}-smena</td>
                    <td className="px-4 py-2 tabular-nums text-emerald-600 dark:text-emerald-400">{shift.coming}</td>
                    <td className="px-4 py-2 tabular-nums text-app-danger">{shift.declined}</td>
                  </tr>
                ))}
              </Table>
            </Card>
          )}

          <Card>
            <div className="flex flex-wrap items-end gap-2 border-b border-app-border px-4 py-3">
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="🔍 Ism yoki familiya"
                className="w-full sm:w-56"
              />
              <Select value={answer} onChange={(e) => setAnswer(e.target.value as '' | RsvpStatus)} className="w-auto">
                <option value="">Barcha javoblar</option>
                <option value="REGISTERED">Qatnashaman</option>
                <option value="DECLINED">Bora olmayman</option>
              </Select>
              {faculties.length > 0 && (
                <Select value={faculty} onChange={(e) => setFaculty(e.target.value)} className="w-auto">
                  <option value="">Barcha fakultet</option>
                  {faculties.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </Select>
              )}
              {courses.length > 0 && (
                <Select value={course} onChange={(e) => setCourse(e.target.value)} className="w-auto">
                  <option value="">Barcha kurs</option>
                  {courses.map((c) => (
                    <option key={c} value={String(c)}>
                      {c}-kurs
                    </option>
                  ))}
                </Select>
              )}
              {groups.length > 0 && (
                <Select value={group} onChange={(e) => setGroup(e.target.value)} className="w-auto">
                  <option value="">Barcha guruh</option>
                  {groups.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </Select>
              )}
              <span className="ml-auto self-center text-sm text-app-hint tabular-nums">{filtered.length} ta</span>
            </div>
            <Table head={["A'zo", 'Fakultet', 'Kurs', 'Guruh', 'Smena', 'Javob', 'Javob vaqti']}>
              {registrations.state.status === 'loading' && <EmptyRow colSpan={7} text="Yuklanmoqda…" />}
              {registrations.state.status === 'success' && filtered.length === 0 && (
                <EmptyRow colSpan={7} text={rows.length === 0 ? 'Hali hech kim javob bermagan' : 'Tanlovga mos a’zo yo‘q'} />
              )}
              {filtered.map((r) => (
                <tr key={r.user_id}>
                  <td className="px-4 py-2 font-medium">
                    {r.last_name} {r.first_name}
                  </td>
                  <td className="px-4 py-2 text-app-hint">{r.faculty_name ?? '—'}</td>
                  <td className="px-4 py-2 tabular-nums">{r.course ?? '—'}</td>
                  <td className="px-4 py-2">{r.group_name ?? '—'}</td>
                  <td className="px-4 py-2">{r.shift != null ? `${r.shift}-smena` : '—'}</td>
                  <td className="px-4 py-2">
                    <Badge tone={ANSWER_TONE[r.status]}>{ANSWER_LABELS[r.status]}</Badge>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-app-hint tabular-nums">{formatDateTime(r.registered_at)}</td>
                </tr>
              ))}
            </Table>
          </Card>
        </div>
      )}
    </>
  )
}
