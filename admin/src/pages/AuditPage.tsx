import { useState } from 'react'

import { MemberScoreHistory } from '../components/ScoreHistory'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Card, EmptyRow, Input, PageHeader, Pagination, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useSession } from '../store/session'
import type { AdminUser, AuditEntry, Page } from '../types/api'
import { formatDateTime } from '../utils/format'

const LIMIT = 50

const ACTION_LABELS: Record<string, string> = {
  ADMIN_LOGIN: 'Admin panelga kirish',
  SUPER_ADMIN_BOOTSTRAP: 'Bosh administrator tayinlandi (sozlama orqali)',
  ADMIN_CREATE: 'Admin tayinlandi',
  ADMIN_PERMISSIONS_CHANGE: "Admin ruxsatlari o'zgartirildi",
  ADMIN_ROLES_CHANGE: "Admin rollari o'zgartirildi",
  ADMIN_DEACTIVATE: 'Admin huquqi olib tashlandi',
  USER_REGISTER: "Ro'yxatdan o'tish",
  USER_UPDATE: "A'zo ma'lumotlari tuzatildi",
  USER_ACTIVATE: 'A\'zo faollashtirildi',
  USER_BLOCK: "A'zo bloklandi",
  USER_DEACTIVATE: "A'zo nofaol qilindi",
  BOOK_CREATE: "Kitob qo'shildi",
  BOOK_UPDATE: 'Kitob tahrirlandi',
  BOOK_DELETE: "Kitob o'chirildi",
  BOOK_READ_VERIFY: "Kitob o'qilgani tasdiqlandi",
  QUOTE_CREATE: "Iqtibos qo'shildi",
  QUOTE_UPDATE: 'Iqtibos tahrirlandi',
  QUOTE_DELETE: "Iqtibos o'chirildi",
  FACULTY_CREATE: "Fakultet qo'shildi",
  FACULTY_UPDATE: "Fakultet o'zgartirildi",
  SETTING_CHANGE: "Sozlama o'zgartirildi",
  ROLE_CREATE: 'Rol yaratildi',
  ROLE_UPDATE: "Rol o'zgartirildi",
  ROLE_DELETE: "Rol o'chirildi",
}

function Changes({ entry }: { entry: AuditEntry }) {
  if (!entry.before && !entry.after) return null
  return (
    <details className="mt-1 text-xs">
      <summary className="cursor-pointer text-app-link">O'zgarishlar</summary>
      <div className="mt-1 grid gap-2 md:grid-cols-2">
        {entry.before && <pre className="overflow-x-auto rounded bg-app-surface p-2">oldin: {JSON.stringify(entry.before, null, 2)}</pre>}
        {entry.after && <pre className="overflow-x-auto rounded bg-app-surface p-2">keyin: {JSON.stringify(entry.after, null, 2)}</pre>}
      </div>
    </details>
  )
}

/** The immutable log of important admin actions. */
function ActionsLog() {
  const { api } = useSession()
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')
  const { state, reload } = useAsync(
    (signal) =>
      api<Page<AuditEntry>>(
        `/api/v1/admin/audit-logs?limit=${LIMIT}&offset=${offset}${action ? `&action=${encodeURIComponent(action)}` : ''}`,
        { signal },
      ),
    [offset, action],
  )

  return (
    <Card>
      <div className="border-b border-app-border p-4">
        <select
          className="w-full max-w-sm rounded-lg border border-app-border bg-app-bg px-3 py-2 text-sm"
          value={action}
          onChange={(e) => {
            setAction(e.target.value)
            setOffset(0)
          }}
          aria-label="Amal turi"
        >
          <option value="">Barcha amallar</option>
          {Object.entries(ACTION_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <>
          <Table head={['Vaqt', 'Kim', 'Amal', 'Sabab']}>
            {state.data.items.length === 0 && <EmptyRow colSpan={4} text="Yozuvlar yo'q" />}
            {state.data.items.map((entry) => (
              <tr key={entry.id} className="align-top">
                <td className="whitespace-nowrap px-4 py-2.5 text-app-hint">{formatDateTime(entry.created_at)}</td>
                <td className="px-4 py-2.5">{entry.actor_name ?? 'Tizim'}</td>
                <td className="px-4 py-2.5">
                  {ACTION_LABELS[entry.action] ?? entry.action}
                  <Changes entry={entry} />
                </td>
                <td className="px-4 py-2.5 text-app-hint">{entry.reason ?? '—'}</td>
              </tr>
            ))}
          </Table>
          <Pagination total={state.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}
    </Card>
  )
}

/** «🧾 A'zo ball tarixi»: pick a member and see why each of their points was given. */
function MemberPoints() {
  const { api } = useSession()
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [selected, setSelected] = useState<{ id: string; name: string } | null>(null)
  const { state } = useAsync(
    (signal) =>
      submitted.trim().length < 2
        ? Promise.resolve(null)
        : api<Page<AdminUser>>(`/api/v1/admin/users?search=${encodeURIComponent(submitted.trim())}&limit=10`, { signal }),
    [submitted],
  )

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h2 className="font-semibold">🧾 A'zo ball tarixi</h2>
        <p className="text-xs text-app-hint">A'zoni ism yoki familiya bo'yicha qidiring — har bir ball unga nega berilganini ko'rasiz.</p>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          setSelected(null)
          setSubmitted(query)
        }}
      >
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ism yoki familiya" maxLength={100} />
        <button type="submit" className="shrink-0 rounded-lg bg-app-button px-4 text-sm font-medium text-app-button-text">
          Qidirish
        </button>
      </form>

      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} />}
      {state.status === 'success' && state.data && !selected && (
        <div className="flex flex-col divide-y divide-app-border/60">
          {state.data.items.length === 0 && <p className="py-4 text-center text-sm text-app-hint">A'zo topilmadi.</p>}
          {state.data.items.map((user) => (
            <button
              key={user.id}
              type="button"
              className="flex items-center justify-between gap-3 py-2.5 text-left hover:bg-app-surface"
              onClick={() => setSelected({ id: user.id, name: `${user.last_name} ${user.first_name}`.trim() })}
            >
              <span className="font-medium">
                {user.last_name} {user.first_name}
              </span>
              <span className="text-xs text-app-hint">
                {[user.faculty_name, user.course ? `${user.course}-kurs` : null, user.group_name].filter(Boolean).join(' · ') || '—'}
              </span>
            </button>
          ))}
        </div>
      )}
      {selected && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <p className="font-medium">{selected.name}</p>
            <button type="button" className="text-sm text-app-link" onClick={() => setSelected(null)}>
              ← Boshqa a'zo
            </button>
          </div>
          <MemberScoreHistory userId={selected.id} open />
        </div>
      )}
    </Card>
  )
}

type Tab = 'actions' | 'points'

export function AuditPage() {
  const [tab, setTab] = useState<Tab>('actions')
  return (
    <>
      <PageHeader title="Audit jurnali" subtitle="Muhim amallar tarixi va a'zolarga berilgan ballar. Yozuvlarni o'zgartirib yoki o'chirib bo'lmaydi." />
      <div className="flex gap-2">
        {(
          [
            ['actions', '📋 Amallar jurnali'],
            ['points', "🧾 A'zo ball tarixi"],
          ] as [Tab, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            className={`rounded-lg border px-3 py-1.5 text-sm ${tab === value ? 'border-app-button bg-app-button/10 font-medium' : 'border-app-border'}`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'actions' ? <ActionsLog /> : <MemberPoints />}
    </>
  )
}
