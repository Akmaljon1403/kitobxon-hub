import type { ReactNode } from 'react'

export function LoadingState({ label = 'Yuklanmoqda…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-center gap-3 py-12 text-app-hint">
      <span className="size-8 animate-spin rounded-full border-2 border-app-hint border-t-transparent" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-4 py-12 text-center">
      <span aria-hidden className="text-3xl">⚠️</span>
      <p className="text-sm text-app-text">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-xl bg-app-button px-5 py-2 text-sm font-medium text-app-button-text active:opacity-80"
        >
          Qayta urinish
        </button>
      )}
    </div>
  )
}

export function EmptyState({ icon = '📭', title, children }: { icon?: string; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-12 text-center">
      <span aria-hidden className="text-3xl">{icon}</span>
      <p className="font-medium">{title}</p>
      {children && <div className="text-sm text-app-hint">{children}</div>}
    </div>
  )
}
