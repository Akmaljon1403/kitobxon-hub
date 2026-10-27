import type { ReactNode } from 'react'

import { Icon, type IconName } from '../components/Icon'
import { useAuth } from '../store/auth'
import { navigate } from '../utils/router'
import { selectionHaptic } from '../utils/telegram'

interface Tab {
  route: string
  icon: IconName
  label: string
  feature?: string
  /** Other sections that keep this tab lit (so deep pages still show where you are). */
  also?: string[]
}

// The five sections of the app. Everything else lives inside one of them or in «Barcha xizmatlar».
const TABS: Tab[] = [
  { route: '', icon: 'home', label: 'Asosiy' },
  { route: 'books', icon: 'book-open', label: 'Mutolaa', also: ['shelf', 'books', 'quotes', 'missions', 'community'] },
  { route: 'events', icon: 'calendar', label: 'Tadbirlar', also: ['checkin'] },
  { route: 'ranking', icon: 'trophy', label: 'Reyting', feature: 'ranking', also: ['league', 'results', 'stats', 'achievements'] },
  {
    route: 'profile',
    icon: 'user',
    label: 'Profil',
    also: ['services', 'certificates', 'rewards', 'premium', 'help', 'invite', 'card'],
  },
]

export function AppLayout({ section, children }: { section: string; children: ReactNode }) {
  const { me } = useAuth()
  // The reader's own shelf («Javonim») is the face of Mutolaa when it is enabled; the club catalogue is
  // one tap away inside it.
  const shelf = me?.features?.shelf === 'on'
  const tabs = TABS.filter((tab) => !tab.feature || me?.features?.[tab.feature] !== 'off').map((tab) =>
    tab.route === 'books' && shelf ? { ...tab, route: 'shelf' } : tab,
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
              <li key={tab.label}>
                <button
                  type="button"
                  onClick={() => go(tab.route)}
                  aria-current={active ? 'page' : undefined}
                  className="group flex w-full flex-col items-center gap-1 py-1 text-[11px] font-medium"
                >
                  <span
                    className={`grid h-8 w-14 place-items-center rounded-full transition-colors ${
                      active ? 'bg-brand-500/15 text-brand-600 dark:text-brand-300' : 'text-app-hint'
                    }`}
                  >
                    <Icon name={tab.icon} size={22} strokeWidth={active ? 2.4 : 2} />
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
