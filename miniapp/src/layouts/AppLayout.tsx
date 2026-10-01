import type { ReactNode } from 'react'

import { navigate } from '../utils/router'

const TABS = [
  { route: '', icon: '🏠', label: 'Asosiy' },
  { route: 'books', icon: '📚', label: 'Kitoblar' },
  { route: 'events', icon: '📅', label: 'Tadbirlar' },
  { route: 'ranking', icon: '🏆', label: 'Reyting' },
  { route: 'profile', icon: '👤', label: 'Profil' },
]

export function AppLayout({ section, children }: { section: string; children: ReactNode }) {
  return (
    <div className="mx-auto min-h-screen max-w-lg pb-24">
      <main className="flex flex-col gap-3 p-3">{children}</main>
      <nav
        aria-label="Asosiy menyu"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-app-hint/15 bg-app-bg/95 backdrop-blur"
        style={{ paddingBottom: 'var(--tg-safe-area-inset-bottom, 0px)' }}
      >
        <ul className="mx-auto grid max-w-lg grid-cols-5">
          {TABS.map((tab) => {
            const active = section === tab.route
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
