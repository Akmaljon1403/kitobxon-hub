import { useEffect, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminAccount, AdminUser, Page, Permission } from '../types/api'

const GROUP_TITLES: Record<string, string> = {
  users: "A'zolar",
  books: 'Kitoblar',
  events: 'Tadbirlar',
  attendance: 'Davomat',
  tests: 'Testlar',
  scores: 'Ballar',
  reports: 'Hisobotlar',
  notifications: 'Xabarlar',
  analytics: 'Statistika',
  rewards: "Sovg'alar",
  seasons: 'Mavsumlar',
  support: 'Murojaatlar',
  payments: "To'lovlar",
  community: "A'zolar fikrlari",
  system: 'Tizim',
}

function PermissionPicker({
  catalogue,
  selected,
  onChange,
}: {
  catalogue: Permission[]
  selected: Set<string>
  onChange: (next: Set<string>) => void
}) {
  const groups = [...new Set(catalogue.map((permission) => permission.group))]
  const toggle = (code: string) => {
    const next = new Set(selected)
    if (next.has(code)) next.delete(code)
    else next.add(code)
    onChange(next)
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {groups.map((group) => (
        <fieldset key={group} className="rounded-lg border border-app-border p-3">
          <legend className="px-1 text-sm font-semibold">{GROUP_TITLES[group] ?? group}</legend>
          {catalogue
            .filter((permission) => permission.group === group)
            .map((permission) => (
              <label key={permission.code} className="flex cursor-pointer items-start gap-2 py-1 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 accent-[var(--app-button)]"
                  checked={selected.has(permission.code)}
                  onChange={() => toggle(permission.code)}
                />
                <span>{permission.description}</span>
              </label>
            ))}
        </fieldset>
      ))}
    </div>
  )
}

export function AdminsPage() {
  const { api, admin } = useSession()
  const { state, reload } = useAsync((signal) => api<AdminAccount[]>('/api/v1/admin/admins', { signal }))
  const catalogue = useAsync((signal) => api<Permission[]>('/api/v1/admin/permissions', { signal }))
  const [editing, setEditing] = useState<AdminAccount | 'new' | null>(null)

  async function dismiss(account: AdminAccount) {
    const reason = window.prompt(
      `${account.first_name} ${account.last_name} admin huquqlaridan mahrum qilinadi (oddiy a'zo bo'lib qoladi).\n\nSababini yozing:`,
    )
    if (!reason) return
    try {
      await api(`/api/v1/admin/admins/${account.user_id}/dismiss`, { method: 'POST', body: { reason } })
      reload()
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    }
  }

  return (
    <>
      <PageHeader
        title="Adminlar"
        subtitle="Har bir adminga faqat kerakli ruxsatlarni bering. Barcha o'zgarishlar audit jurnaliga yoziladi."
        actions={<Button onClick={() => setEditing('new')}>+ Admin tayinlash</Button>}
      />
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={['Admin', 'Rol', 'Ruxsatlar', '']}>
            {state.data.length === 0 && <EmptyRow colSpan={4} text="Adminlar yo'q" />}
            {state.data.map((account) => {
              const isSuper = account.roles.includes('SUPER_ADMIN')
              return (
                <tr key={account.user_id}>
                  <td className="px-4 py-2.5">
                    <p className="font-medium">
                      {account.first_name} {account.last_name}
                    </p>
                    {account.telegram_username && <p className="text-xs text-app-hint">@{account.telegram_username}</p>}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone={isSuper ? 'info' : 'neutral'}>{isSuper ? 'Bosh administrator' : 'Administrator'}</Badge>
                  </td>
                  <td className="px-4 py-2.5 text-app-hint">
                    {isSuper ? 'Barcha ruxsatlar' : `${account.effective_permissions.length} ta ruxsat`}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-right">
                    {!isSuper && (
                      <Button variant="ghost" onClick={() => setEditing(account)}>
                        Ruxsatlar
                      </Button>
                    )}
                    {account.user_id !== admin?.id && (
                      <Button variant="ghost" className="text-app-danger" onClick={() => void dismiss(account)}>
                        Olib tashlash
                      </Button>
                    )}
                  </td>
                </tr>
              )
            })}
          </Table>
        )}
      </Card>
      {editing && catalogue.state.status === 'success' && (
        <AdminModal
          account={editing === 'new' ? null : editing}
          catalogue={catalogue.state.data}
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

// Typical jobs in the club. "To'liq admin" means every permission (managing admins stays with super admins).
const PRESETS: { label: string; hint: string; permissions?: string[] }[] = [
  { label: "⭐ To'liq admin", hint: 'Barcha ruxsatlar' },
  {
    label: '📅 Tadbir va davomat',
    hint: "Tadbir yaratish, davomatni ochish va tuzatish",
    permissions: ['EVENT_VIEW', 'EVENT_CREATE', 'EVENT_EDIT', 'ATTENDANCE_VIEW', 'ATTENDANCE_MANAGE', 'USER_VIEW'],
  },
  {
    label: '📚 Kitob va testlar',
    hint: "Kitob, iqtibos va testlarni boshqarish",
    permissions: ['BOOK_VIEW', 'BOOK_CREATE', 'BOOK_EDIT', 'TEST_VIEW', 'TEST_CREATE', 'TEST_EDIT', 'TEST_PUBLISH'],
  },
  {
    label: "🏆 Ballar va sovg'alar",
    hint: "Ballarni qo'lda berish, mavsumlar, sovg'alar",
    permissions: ['USER_VIEW', 'SCORE_VIEW', 'SCORE_MANAGE', 'REWARD_MANAGE', 'SEASON_MANAGE'],
  },
  {
    label: '📨 Xabar va murojaatlar',
    hint: "A'zolarga xabar yuborish, murojaatlarga javob berish va a'zolar fikrlarini ulashish",
    permissions: ['USER_VIEW', 'NOTIFICATION_SEND', 'SUPPORT_MANAGE', 'COMMUNITY_MANAGE'],
  },
  {
    label: "💳 To'lov savollari",
    hint: "To'lov bo'yicha savollarga botda va to'lovlar kanalining o'zida javob berish",
    permissions: ['USER_VIEW', 'SUPPORT_MANAGE', 'PAYMENT_SUPPORT'],
  },
  {
    label: '📄 Hisobot va tahlil',
    hint: 'Rasmiy hisobotlar va statistika',
    permissions: ['EVENT_VIEW', 'REPORT_VIEW', 'REPORT_CREATE', 'REPORT_APPROVE', 'ANALYTICS_VIEW'],
  },
]

function AdminModal({
  account,
  catalogue,
  onClose,
  onSaved,
}: {
  account: AdminAccount | null
  catalogue: Permission[]
  onClose: () => void
  onSaved: () => void
}) {
  const { api } = useSession()
  const [selected, setSelected] = useState(new Set(account?.direct_permissions ?? []))
  const [search, setSearch] = useState('')
  const [results, setResults] = useState<AdminUser[]>([])
  const [member, setMember] = useState<AdminUser | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (account || search.trim().length < 2) {
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
  }, [search, account, api])

  async function save() {
    setBusy(true)
    setError(null)
    try {
      if (account) {
        await api(`/api/v1/admin/admins/${account.user_id}/permissions`, {
          method: 'PUT',
          body: { permissions: [...selected] },
        })
      } else if (member) {
        await api('/api/v1/admin/admins', { method: 'POST', body: { user_id: member.id, permissions: [...selected] } })
      }
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={account ? `${account.first_name} ${account.last_name} — ruxsatlar` : 'Admin tayinlash'}
      onClose={onClose}
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button onClick={() => void save()} loading={busy} disabled={!account && !member}>
            Saqlash
          </Button>
        </>
      }
    >
      {!account && (
        <Field label="1. A'zoni toping" hint="Admin faqat botda ro'yxatdan o'tgan faol a'zo bo'lishi mumkin">
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
            <>
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Ism yoki familiya…" />
              {results.length > 0 && (
                <ul className="mt-1 divide-y divide-app-border rounded-lg border border-app-border">
                  {results.map((user) => (
                    <li key={user.id}>
                      <button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-app-surface" onClick={() => setMember(user)}>
                        {user.last_name} {user.first_name}
                        <span className="text-app-hint"> · {user.faculty_name ?? ''} {user.group_name ?? ''}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </Field>
      )}
      <p className="text-sm font-medium">{account ? 'Ruxsatlar' : '2. Ruxsatlarni belgilang'}</p>
      <div className="flex flex-col gap-2 rounded-lg bg-app-surface p-3">
        <p className="text-xs text-app-hint">Tayyor lavozimlar — bosilsa, kerakli ruxsatlar belgilanadi (keyin o'zgartirsa bo'ladi):</p>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((preset) => {
            const codes = preset.permissions ?? catalogue.map((item) => item.code)
            const active = codes.every((code) => selected.has(code))
            return (
              <button
                key={preset.label}
                type="button"
                title={preset.hint}
                aria-pressed={active}
                onClick={() => setSelected(new Set([...selected, ...codes]))}
                className={`rounded-full border px-3 py-1 text-sm transition ${active ? 'border-app-button bg-app-button text-app-button-text' : 'border-app-border bg-app-bg hover:bg-app-surface'}`}
              >
                {preset.label}
              </button>
            )
          })}
          <button type="button" onClick={() => setSelected(new Set())} className="rounded-full px-3 py-1 text-sm text-app-hint hover:text-app-text">
            Tozalash
          </button>
        </div>
      </div>
      <PermissionPicker catalogue={catalogue} selected={selected} onChange={setSelected} />
      <InlineError message={error} />
    </Modal>
  )
}
