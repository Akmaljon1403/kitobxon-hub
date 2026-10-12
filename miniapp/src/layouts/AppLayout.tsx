import type { ReactNode } from 'react'

import { useAuth } from '../store/auth'
import { navigate } from '../utils/router'

interface Tab {
  route: string
  icon: string
  label: string
  feature?: string
  // other sections that light this tab up (the library: shelf, club books, quotes, missions)
  also?: string[]
}

const LIBRARY = ['shelf', 'books', 'quotes', 'missions', 'community']

const TABS: Tab[] = [
  { route: '', icon: '🏠', label: 'Asosiy' },
  { route: 'books', icon: '📚', label: 'Kitoblar', also: LIBRARY },
  { route: 'events', icon: '📅', label: 'Tadbirlar' },
  { route: 'ranking', icon: '🏆', label: 'Reyting', feature: 'ranking' },
  { route: 'profile', icon: '👤', label: 'Profil' },
]

export function AppLayout({ section, children }: { section: string; children: ReactNode }) {
  const { me } = useAuth()
  // «📚 Javonim» stands in for «Kitoblar» once the shelf is open: a reader's own books first, the club's
  // catalogue one tap away inside it.
  const shelf = me?.features?.shelf === 'on'
  const tabs = TABS.filter((tab) => !tab.feature || me?.features?.[tab.feature] !== 'off').map((tab) =>
    tab.route === 'books' && shelf ? { ...tab, route: 'shelf', label: 'Javonim' } : tab,
  )
  return (
    <div className="mx-auto min-h-screen max-w-lg pb-24">
      <main className="flex flex-col gap-3 p-3">{children}</main>
      <nav
        aria-label="Asosiy menyu"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-app-hint/15 bg-app-bg/95 backdrop-blur"
        style={{ paddingBottom: 'var(--tg-safe-area-inset-bottom, 0px)' }}
      >
        <ul className={`mx-auto grid max-w-lg ${tabs.length === 5 ? 'grid-cols-5' : 'grid-cols-4'}`}>
          {tabs.map((tab) => {
            const active = section === tab.route || Boolean(tab.also?.includes(section))
            return (
              <li key={tab.route}>
                <button
                  type="button"
                  onClick={() => navigate(`/${tab.route}`)}
                  aria-current={active ? 'page' : undefined}
                  className={`flex w-full flex-col items-center gap-0.5 py-2 text-[11px] ${active ? 'font-semibold text-app-button' : 'text-app-hint'}`}
                >
                  <span aria-hidden className="text-xl leading-none">
                    {tab.icon}
                  </span>
                  {tab.label}
                </button>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}
