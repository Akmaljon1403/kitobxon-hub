import { useState, type ReactNode } from 'react'

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
  { route: 'members', icon: '👥', label: "A'zolar", visible: (can) => can('USER_VIEW') },
  { route: 'books', icon: '📚', label: 'Kitoblar', visible: (can) => can('BOOK_VIEW') },
  { route: 'quotes', icon: '💬', label: 'Iqtiboslar', visible: (can) => can('BOOK_VIEW') },
  { route: 'events', icon: '📅', label: 'Tadbirlar va davomat', visible: (can) => can('EVENT_VIEW') },
  { route: 'tests', icon: '📝', label: 'Testlar', visible: (can) => can('TEST_VIEW') },
  { route: 'scores', icon: '🏆', label: 'Ballar va reyting', visible: (can) => can('SCORE_VIEW') },
  { route: 'faculties', icon: '🏛', label: 'Fakultetlar', visible: () => true },
  { route: 'settings', icon: '⚙️', label: 'Sozlamalar', visible: () => true },
  { route: 'admins', icon: '🛡', label: 'Adminlar', visible: (_, isSuper) => isSuper },
  { route: 'audit', icon: '🧾', label: 'Audit jurnali', visible: (can) => can('AUDIT_LOG_VIEW') },
]

export function AdminLayout({ section, children }: { section: string; children: ReactNode }) {
  const { admin, can, logout } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
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
            {item.label}
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
