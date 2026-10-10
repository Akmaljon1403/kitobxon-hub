import { useEffect, useRef, useState } from 'react'

import { useSession } from '../store/session'
import { navigate } from '../utils/router'

interface SearchItem {
  kind: string
  title: string
  subtitle: string | null
  route: string | null
}

const ICONS: Record<string, string> = {
  member: '👤',
  book: '📚',
  event: '📅',
  test: '📝',
  reward: '🎁',
  page: '🧭',
  setting: '⚙️',
  command: '🤖',
}

/** One box for everything: members, books, events, tests, settings, pages and bot commands («stiker»...). */
export function GlobalSearch() {
  const { api } = useSession()
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<SearchItem[]>([])
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) {
      setItems([])
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      api<SearchItem[]>(`/api/v1/admin/search?q=${encodeURIComponent(q)}`, { signal: controller.signal })
        .then((found) => {
          setItems(found)
          setOpen(true)
        })
        .catch(() => undefined)
    }, 250)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [api, query])

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (box.current && !box.current.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  function go(item: SearchItem) {
    if (!item.route) return
    setOpen(false)
    setQuery('')
    navigate(`/${item.route}`)
  }

  return (
    <div ref={box} className="relative w-full max-w-xs">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => items.length && setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            const first = items.find((item) => item.route)
            if (first) go(first)
          } else if (e.key === 'Escape') setOpen(false)
        }}
        placeholder="🔎 Qidirish: a'zo, kitob, «stiker»..."
        aria-label="Hamma joydan qidirish"
        className="w-full rounded-lg border border-app-border bg-app-surface px-3 py-1.5 text-sm outline-none focus:border-app-button"
      />
      {open && query.trim().length >= 2 && (
        <div className="absolute right-0 z-30 mt-1 max-h-96 w-[min(28rem,90vw)] overflow-y-auto rounded-xl border border-app-border bg-app-bg p-1 shadow-lg">
          {items.length === 0 && <p className="p-3 text-sm text-app-hint">Hech narsa topilmadi.</p>}
          {items.map((item, index) => (
            <button
              key={`${item.kind}-${index}`}
              type="button"
              disabled={!item.route}
              onClick={() => go(item)}
              className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-app-surface disabled:cursor-default disabled:hover:bg-transparent"
            >
              <span aria-hidden>{ICONS[item.kind] ?? '•'}</span>
              <span className="min-w-0">
                <span className="block truncate font-medium">{item.title}</span>
                {item.subtitle && <span className="block truncate text-xs text-app-hint">{item.subtitle}</span>}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
