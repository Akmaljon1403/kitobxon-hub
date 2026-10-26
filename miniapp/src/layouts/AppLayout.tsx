import type { ReactNode } from 'react'

import { useAuth } from '../store/auth'
import { navigate } from '../utils/router'
import { selectionHaptic } from '../utils/telegram'

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
  const go = (route: string) => {
    selectionHaptic()
    navigate(`/${route}`)
  }
  return (
    <div className="mx-auto min-h-screen max-w-lg pb-[calc(5.25rem+var(--tg-safe-area-inset-bottom,0px))]">
      {/* key=section re-triggers the entrance on every navigation. Opacity only — a transform here would
          reparent position:fixed overlays/modals (test runner, dialogs) to this wrapper, breaking them. */}
      <main key={section} className="animate-fade-in flex flex-col gap-3 px-4 pb-4 pt-3">
        {children}
      </main>
      <nav
        aria-label="Asosiy menyu"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-[color:var(--hairline)] bg-app-bg/90 backdrop-blur-lg"
        style={{ paddingBottom: 'var(--tg-safe-area-inset-bottom, 0px)' }}
      >
        <ul className={`mx-auto grid max-w-lg px-2 py-1.5 ${tabs.length === 5 ? 'grid-cols-5' : 'grid-cols-4'}`}>
          {tabs.map((tab) => {
            const active = section === tab.route || Boolean(tab.also?.includes(section))
            return (
              <li key={tab.route}>
                <button
                  type="button"
                  onClick={() => go(tab.route)}
                  aria-current={active ? 'page' : undefined}
                  className="group flex w-full flex-col items-center gap-1 py-1.5 text-[11px] font-medium"
                >
                  <span
                    aria-hidden
                    className={`grid h-7 w-14 place-items-center rounded-full text-xl leading-none transition-colors ${
                      active ? 'bg-brand-500/15 text-brand-600 dark:text-brand-300' : 'text-app-hint'
                    }`}
                  >
                    {tab.icon}
                  </span>
                  <span className={active ? 'font-semibold text-brand-600 dark:text-brand-300' : 'text-app-hint'}>
                    {tab.label}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}
