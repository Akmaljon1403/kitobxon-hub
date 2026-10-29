import { useEffect, type ReactNode } from 'react'

import { Icon } from './Icon'

/**
 * A mobile-first bottom sheet (drawer): the panel slides up over a dimmed backdrop. Used for
 * detail views that should not navigate away from the current screen — e.g. the breakdown behind
 * one points entry. Closes on the backdrop, the ✕ button or Escape. Motion is disabled under
 * `prefers-reduced-motion` (see index.css), and the panel respects the Telegram safe area.
 */
export function BottomSheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  title?: ReactNode
  children: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Yopish"
        onClick={onClose}
        className="animate-backdrop-in absolute inset-0 bg-navy-950/45 backdrop-blur-[2px]"
      />
      <div
        className="animate-sheet-up relative flex w-full max-w-lg flex-col rounded-t-3xl bg-app-bg ring-1 ring-app-hint/10"
        style={{
          paddingBottom: 'calc(1.25rem + var(--tg-safe-area-inset-bottom, 0px))',
          boxShadow: '0 -14px 44px rgba(5, 14, 29, 0.32)',
        }}
      >
        <div className="flex justify-center pt-2.5">
          <span className="h-1.5 w-10 rounded-full bg-app-hint/30" />
        </div>
        {title && (
          <div className="flex items-center justify-between gap-2 px-5 pb-1 pt-3">
            <h2 className="font-serif text-lg font-bold">{title}</h2>
            <button
              type="button"
              aria-label="Yopish"
              onClick={onClose}
              className="grid size-8 shrink-0 place-items-center rounded-full bg-app-surface text-app-hint transition active:scale-90"
            >
              <Icon name="x" size={18} />
            </button>
          </div>
        )}
        <div className="max-h-[75vh] overflow-y-auto px-5 pt-2">{children}</div>
      </div>
    </div>
  )
}
