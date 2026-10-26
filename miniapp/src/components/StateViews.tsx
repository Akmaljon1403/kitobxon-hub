import type { ReactNode } from 'react'

import { Skeleton } from './ui'

export function LoadingState({ label = 'Yuklanmoqda…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-center gap-3 py-12 text-app-hint">
      <span className="size-8 animate-spin rounded-full border-2 border-app-hint border-t-transparent" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

/** A content-shaped placeholder for the first paint — calmer than a spinner for lists of cards. */
export function CardListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className="flex flex-col gap-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="rounded-2xl border border-[color:var(--hairline)] bg-app-bg p-4 shadow-[var(--shadow-card)]">
          <div className="flex items-center gap-3">
            <Skeleton className="size-11 rounded-xl" />
            <div className="flex flex-1 flex-col gap-2">
              <Skeleton className="h-3.5 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-4 py-14 text-center">
      <span aria-hidden className="grid size-14 place-items-center rounded-2xl bg-app-danger/12 text-3xl">
        ⚠️
      </span>
      <p className="max-w-xs text-sm text-app-text">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-xl bg-brand-gradient px-5 py-2 text-sm font-semibold text-white shadow-[var(--shadow-brand)] active:scale-[0.97]"
        >
          Qayta urinish
        </button>
      )}
    </div>
  )
}

export function EmptyState({ icon = '📭', title, children }: { icon?: string; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-14 text-center">
      <span aria-hidden className="grid size-16 place-items-center rounded-3xl bg-app-surface text-4xl">
        {icon}
      </span>
      <p className="font-semibold text-balance">{title}</p>
      {children && <div className="max-w-xs text-sm text-app-hint">{children}</div>}
    </div>
  )
}
