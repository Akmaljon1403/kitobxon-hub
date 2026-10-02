import { useEffect, useState, type ReactNode } from 'react'

import { useSession } from '../store/session'
import { navigate } from '../utils/router'

export interface NavItem {
  route: string
  icon: string
  label: string
  visible: (can: (p: string) => boolean, isSuper: boolean) => boolean
}

export const NAV_ITEMS: NavItem[] = [
  { route: '', icon: '📊', label: 'Bosh sahifa', visible: () => true },
  { route: 'analytics', icon: '📈', label: 'Tahlillar', visible: (can) => can('ANALYTICS_VIEW') },
  { route: 'members', icon: '👥', label: "A'zolar", visible: (can) => can('USER_VIEW') },
  { route: 'books', icon: '📚', label: 'Kitoblar', visible: (can) => can('BOOK_VIEW') },
  { route: 'quotes', icon: '💬', label: 'Iqtiboslar', visible: (can) => can('BOOK_VIEW') },
  { route: 'events', icon: '📅', label: 'Tadbirlar va davomat', visible: (can) => can('EVENT_VIEW') },
  { route: 'tests', icon: '📝', label: 'Testlar', visible: (can) => can('TEST_VIEW') },
  { route: 'scores', icon: '🏆', label: 'Ballar va reyting', visible: (can) => can('SCORE_VIEW') },
  { route: 'reports', icon: '📄', label: 'Hisobotlar', visible: (can) => can('REPORT_VIEW') },
  { route: 'achievements', icon: '🏅', label: 'Yutuqlar', visible: () => true },
  { route: 'rewards', icon: '🎁', label: "Sovg'alar", visible: (can) => can('REWARD_MANAGE') },
  { route: 'certificates', icon: '🎓', label: 'Sertifikatlar', visible: (can) => can('REWARD_MANAGE') },
  { route: 'support', icon: '📨', label: 'Murojaatlar', visible: (can) => can('SUPPORT_MANAGE') },
  { route: 'notifications', icon: '📢', label: 'Xabarlar', visible: (can) => can('NOTIFICATION_SEND') },
  { route: 'faculties', icon: '🏛', label: 'Fakultetlar', visible: () => true },
  { route: 'settings', icon: '⚙️', label: 'Sozlamalar', visible: () => true },
  { route: 'admins', icon: '🛡', label: 'Adminlar', visible: (_, isSuper) => isSuper },
  { route: 'audit', icon: '🧾', label: 'Audit jurnali', visible: (can) => can('AUDIT_LOG_VIEW') },
]

/** Conversations waiting for an answer, refreshed every minute (shown next to «Murojaatlar»). */
function useUnreadSupport(): number {
  const { api, can } = useSession()
  const allowed = can('SUPPORT_MANAGE')
  const [count, setCount] = useState(0)
  useEffect(() => {
    if (!allowed) return
    let stopped = false
    const load = () =>
      api<{ unread: number }>('/api/v1/admin/support/summary')
        .then((result) => !stopped && setCount(result.unread))
        .catch(() => undefined)
    void load()
    const timer = window.setInterval(load, 60_000)
    return () => {
      stopped = true
      window.clearInterval(timer)
    }
  }, [allowed, api])
  return count
}

export function AdminLayout({ section, children }: { section: string; children: ReactNode }) {
  const { admin, can, logout } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
  const unread = useUnreadSupport()
  const items = NAV_ITEMS.filter((item) => item.visible(can, Boolean(admin?.is_super_admin)))

  const nav = (
    <nav aria-label="Bo'limlar" className="flex flex-col gap-0.5 p-3">
      {items.map((item) => {
        const active = section === item.route
        return (
          <button
            key={item.route}
            type="button"
            aria-current={active ? 'page' : undefined}
            onClick={() => {
              navigate(`/${item.route}`)
              setMenuOpen(false)
            }}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-left text-sm ${
              active ? 'bg-app-button/10 font-semibold text-app-button' : 'text-app-text hover:bg-app-surface'
            }`}
          >
            <span aria-hidden className="w-5 text-center">
              {item.icon}
            </span>
            <span className="flex-1">{item.label}</span>
            {item.route === 'support' && unread > 0 && (
              <span className="rounded-full bg-app-danger px-2 py-0.5 text-xs font-semibold text-white" aria-label={`${unread} ta yangi`}>
                {unread}
              </span>
            )}
          </button>
        )
      })}
    </nav>
  )

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      <aside className="hidden border-r border-app-border bg-app-bg lg:flex lg:min-h-screen lg:flex-col">
        <div className="border-b border-app-border px-5 py-4">
          <p className="font-semibold">📚 Kitobxon Hub</p>
          <p className="text-xs text-app-hint">Admin panel</p>
        </div>
        {nav}
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-app-border bg-app-bg/95 px-4 py-2.5 backdrop-blur">
          <button
            type="button"
            className="rounded-lg px-2 py-1 text-xl lg:hidden"
            aria-label="Menyu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            ☰
          </button>
          <p className="font-semibold lg:hidden">Kitobxon Hub</p>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="hidden text-app-hint sm:inline">
              {admin?.first_name} {admin?.last_name}
              {admin?.is_super_admin ? ' · Bosh administrator' : ' · Administrator'}
            </span>
            <button type="button" onClick={() => void logout()} className="text-app-link hover:underline">
              Chiqish
            </button>
          </div>
        </header>
        {menuOpen && <div className="border-b border-app-border bg-app-bg lg:hidden">{nav}</div>}
        <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  )
}
