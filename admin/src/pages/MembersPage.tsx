import { useEffect, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Pagination, Select, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import { useRoute } from '../utils/router'
import type { AdminUser, Faculty, Page, UserStatus } from '../types/api'
import { USER_STATUS_LABELS, formatDate, formatDateTime } from '../utils/format'

const LIMIT = 50
const STATUS_TONE: Record<UserStatus, 'success' | 'warning' | 'danger' | 'neutral'> = {
  ACTIVE: 'success',
  PENDING: 'warning',
  BLOCKED: 'danger',
  INACTIVE: 'neutral',
  LEFT: 'neutral',
}
const LEFT_REASONS: Record<string, string> = {
  BOT_BLOCKED: 'botni bloklagan',
  CANCELLED: 'admin bekor qilgan',
  SELF: "o'zi chiqqan",
}

function daysSince(value: string | null | undefined): number {
  return value ? Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000) : 0
}

export function StatusBadge({ status }: { status: UserStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{USER_STATUS_LABELS[status]}</Badge>
}

function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

export function MembersPage() {
  const { api, can } = useSession()
  const route = useRoute()
  const [search, setSearch] = useState(route.query.get('q') ?? '')  // from the search box in the header
  const [status, setStatus] = useState('')
  const [facultyId, setFacultyId] = useState('')
  const [course, setCourse] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const query = useDebounced(search)

  useEffect(() => setOffset(0), [query, status, facultyId, course])

  const faculties = useAsync((signal) => api<Faculty[]>('/api/v1/admin/faculties', { signal }))
  const params = new URLSearchParams({ limit: String(LIMIT), offset: String(offset) })
  if (query.trim()) params.set('search', query.trim())
  if (status) params.set('status', status)
  if (facultyId) params.set('faculty_id', facultyId)
  if (course) params.set('course', course)
  const { state, reload } = useAsync(
    (signal) => api<Page<AdminUser>>(`/api/v1/admin/users?${params}`, { signal }),
    [params.toString()],
  )
  const showPhone = can('USER_CONTACT_VIEW')

  return (
    <>
      <PageHeader title="A'zolar" subtitle="Ro'yxatdan o'tgan klub a'zolari" />
      <Card>
        <div className="grid gap-3 border-b border-app-border p-4 sm:grid-cols-2 lg:grid-cols-4">
          <Input
            type="search"
            placeholder={showPhone ? 'Ism, guruh, telefon…' : 'Ism, familiya yoki guruh…'}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Qidirish"
          />
          <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Holat">
            <option value="">Barcha holatlar</option>
            {Object.entries(USER_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          <Select value={facultyId} onChange={(e) => setFacultyId(e.target.value)} aria-label="Fakultet">
            <option value="">Barcha fakultetlar</option>
            {faculties.state.status === 'success' &&
              faculties.state.data.map((faculty) => (
                <option key={faculty.id} value={faculty.id}>
                  {faculty.name}
                </option>
              ))}
          </Select>
          <Select value={course} onChange={(e) => setCourse(e.target.value)} aria-label="Kurs">
            <option value="">Barcha kurslar</option>
            {[1, 2, 3, 4, 5, 6, 7].map((n) => (
              <option key={n} value={n}>
                {n}-kurs
              </option>
            ))}
          </Select>
        </div>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <>
            <Table head={["F.I.Sh.", 'Fakultet', 'Kurs / guruh', ...(showPhone ? ['Telefon'] : []), 'Holat', "Ro'yxatdan o'tgan"]}>
              {state.data.items.length === 0 && <EmptyRow colSpan={showPhone ? 6 : 5} text="Hech kim topilmadi" />}
              {state.data.items.map((user) => (
                <tr key={user.id} onClick={() => setSelected(user.id)} className="cursor-pointer hover:bg-app-surface">
                  <td className="px-4 py-2.5">
                    <p className="font-medium">
                      {user.last_name} {user.first_name}
                    </p>
                    {user.telegram_username && <p className="text-xs text-app-hint">@{user.telegram_username}</p>}
                  </td>
                  <td className="px-4 py-2.5">{user.faculty_name ?? '—'}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    {user.course ? `${user.course}-kurs` : '—'} · {user.group_name ?? '—'}
                    {user.graduated_at && <span title="Bitiruvchi"> 🎓</span>}
                  </td>
                  {showPhone && <td className="whitespace-nowrap px-4 py-2.5 tabular-nums">{user.phone ?? '—'}</td>}
                  <td className="px-4 py-2.5">
                    <StatusBadge status={user.status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-app-hint">{formatDate(user.registered_at)}</td>
                </tr>
              ))}
            </Table>
            <Pagination total={state.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
      {selected && (
        <MemberModal
          userId={selected}
          faculties={faculties.state.status === 'success' ? faculties.state.data : []}
          onClose={() => setSelected(null)}
          onChanged={reload}
        />
      )}
    </>
  )
}

function MemberModal({
  userId,
  faculties,
  onClose,
  onChanged,
}: {
  userId: string
  faculties: Faculty[]
  onClose: () => void
  onChanged: () => void
}) {
  const { api, can, admin } = useSession()
  const { state, reload } = useAsync((signal) => api<AdminUser>(`/api/v1/admin/users/${userId}`, { signal }), [userId])
  const [form, setForm] = useState<Partial<AdminUser> | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const canManage = can('USER_MANAGE')

  useEffect(() => {
    if (state.status === 'success') setForm(state.data)
  }, [state])

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      reload()
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(false)
    }
  }

  function save() {
    if (!form) return
    return run(() =>
      api(`/api/v1/admin/users/${userId}`, {
        method: 'PATCH',
        body: {
          first_name: form.first_name,
          last_name: form.last_name,
          faculty_id: form.faculty_id || null,
          course: form.course ? Number(form.course) : undefined,
          group_name: form.group_name,
          graduated: Boolean(form.graduated_at),
        },
      }),
    )
  }

  function cancelMembership() {
    const reason = window.prompt(
      "A'zolikni bekor qilasizmi? A'zo xabarlar olmaydi va reytingda ko'rinmaydi. Ma'lumotlari 30 kun saqlanadi — u so'rov yuborib qaytishi mumkin, keyin avtomatik o'chiriladi.\n\nSababini yozing (a'zo ko'radi):",
    )
    if (!reason || reason.trim().length < 5) return
    return run(() => api(`/api/v1/admin/users/${userId}/cancel-membership`, { method: 'POST', body: { reason } }))
  }

  function erase() {
    const reason = window.prompt(
      "⚠️ A'zoning shaxsiy ma'lumotlari (ism, telefon, Telegram, rasmlar, cheklar, xabarlar) BUTUNLAY o'chiriladi. Qaytarib bo'lmaydi.\n\nSababini yozing:",
    )
    if (!reason || reason.trim().length < 5) return
    const confirm = window.prompt("Tasdiqlash uchun O'CHIRISH deb yozing:")
    if (!confirm) return
    return run(async () => {
      await api(`/api/v1/admin/users/${userId}/erase`, { method: 'POST', body: { reason, confirm } })
      onClose()
    })
  }

  function changeStatus(status: UserStatus, question: string) {
    const reason = window.prompt(`${question}\n\nSababini yozing (kamida 5 belgi):`)
    if (!reason) return
    return run(() => api(`/api/v1/admin/users/${userId}/status`, { method: 'POST', body: { status, reason } }))
  }

  return (
    <Modal title="A'zo ma'lumotlari" onClose={onClose} wide>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && form && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={state.data.status} />
            {state.data.graduated_at && <Badge tone="info">🎓 Bitiruvchi</Badge>}
            {state.data.roles?.map((role) => (
              <Badge key={role} tone="info">
                {role}
              </Badge>
            ))}
            <span className="text-xs text-app-hint">Oxirgi faollik: {formatDateTime(state.data.last_seen_at)}</span>
          </div>
          {state.data.status === 'LEFT' && (
            <p className="rounded-lg bg-app-surface px-3 py-2 text-sm">
              🚪 {daysSince(state.data.left_at)} kun oldin klubdan chiqqan ({LEFT_REASONS[state.data.left_reason ?? ''] ?? '—'}). Ma'lumotlari{' '}
              {Math.max(30 - daysSince(state.data.left_at), 0)} kundan keyin avtomatik o'chiriladi.
              {state.data.restore_requested_at && <b> 📨 Tiklash so'rovini yuborgan.</b>}
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Ism">
              <Input value={form.first_name ?? ''} disabled={!canManage} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
            </Field>
            <Field label="Familiya">
              <Input value={form.last_name ?? ''} disabled={!canManage} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
            </Field>
            <Field label="Fakultet">
              <Select value={form.faculty_id ?? ''} disabled={!canManage} onChange={(e) => setForm({ ...form, faculty_id: e.target.value })}>
                <option value="">Tanlanmagan</option>
                {faculties.map((faculty) => (
                  <option key={faculty.id} value={faculty.id}>
                    {faculty.name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Kurs">
                <Input
                  type="number"
                  min={1}
                  max={8}
                  value={form.course ?? ''}
                  disabled={!canManage}
                  onChange={(e) => setForm({ ...form, course: Number(e.target.value) })}
                />
              </Field>
              <Field label="Guruh">
                <Input value={form.group_name ?? ''} disabled={!canManage} onChange={(e) => setForm({ ...form, group_name: e.target.value })} />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={Boolean(form.graduated_at)}
                disabled={!canManage}
                onChange={(e) => setForm({ ...form, graduated_at: e.target.checked ? new Date().toISOString() : null })}
              />
              🎓 Bitiruvchi (o'qishni tamomlagan; klubda qoladi, kurs hisobotlariga kirmaydi)
            </label>
            {state.data.phone && (
              <Field label="Telefon">
                <Input value={state.data.phone} disabled />
              </Field>
            )}
            <Field label="Ro'yxatdan o'tgan">
              <Input value={formatDateTime(state.data.registered_at)} disabled />
            </Field>
          </div>
          <InlineError message={error} />
          {canManage && (
            <div className="flex flex-wrap justify-between gap-2 border-t border-app-border pt-4">
              <div className="flex flex-wrap gap-2">
                {state.data.status === 'PENDING' && (
                  <Button onClick={() => changeStatus('ACTIVE', "A'zoni tasdiqlaysizmi?")} loading={busy}>
                    ✅ Tasdiqlash
                  </Button>
                )}
                {state.data.status === 'ACTIVE' && (
                  <Button variant="danger" onClick={() => changeStatus('BLOCKED', "A'zoni bloklaysizmi?")} loading={busy}>
                    Bloklash
                  </Button>
                )}
                {state.data.status !== 'LEFT' && (
                  <Button variant="secondary" onClick={() => void cancelMembership()} loading={busy}>
                    🚪 A'zolikni bekor qilish
                  </Button>
                )}
                {state.data.status === 'LEFT' && (
                  <Button onClick={() => void run(() => api(`/api/v1/admin/users/${userId}/restore`, { method: 'POST' }))} loading={busy}>
                    ♻️ A'zolikni tiklash
                  </Button>
                )}
                {admin?.is_super_admin && (
                  <Button variant="danger" onClick={() => void erase()} loading={busy}>
                    🗑 Ma'lumotlarini o'chirish
                  </Button>
                )}
                {(state.data.status === 'BLOCKED' || state.data.status === 'INACTIVE') && (
                  <Button variant="secondary" onClick={() => changeStatus('ACTIVE', 'Hisobni qayta faollashtirasizmi?')} loading={busy}>
                    Faollashtirish
                  </Button>
                )}
                <Button
                  variant="secondary"
                  loading={busy}
                  onClick={() => {
                    if (window.confirm("A'zo yuklagan pasport rasmi o'chirilsinmi? Pasportda Telegram rasmi qoladi."))
                      void run(() => api(`/api/v1/admin/users/${userId}/passport-photo`, { method: 'DELETE' }))
                  }}
                >
                  🖼 Pasport rasmini o'chirish
                </Button>
              </div>
              <Button onClick={save} loading={busy}>
                Saqlash
              </Button>
            </div>
          )}
        </>
      )}
    </Modal>
  )
}
