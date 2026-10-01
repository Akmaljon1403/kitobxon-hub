import type { ButtonHTMLAttributes, ReactNode } from 'react'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl bg-app-bg p-4 shadow-sm ${className}`}>{children}</section>
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="px-1 pb-2 pt-1 text-xs font-semibold uppercase tracking-wide text-app-hint">{children}</h2>
}

type Variant = 'primary' | 'secondary' | 'ghost'

export function Button({
  variant = 'primary',
  loading = false,
  className = '',
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  const styles: Record<Variant, string> = {
    primary: 'bg-app-button text-app-button-text',
    secondary: 'bg-app-surface text-app-text',
    ghost: 'bg-transparent text-app-link',
  }
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={`flex min-h-11 w-full items-center justify-center gap-2 rounded-xl px-4 text-[15px] font-medium transition-opacity active:opacity-70 disabled:opacity-50 ${styles[variant]} ${className}`}
      {...rest}
    >
      {loading && <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  )
}

type Tone = 'neutral' | 'success' | 'info' | 'warning'

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  const tones: Record<Tone, string> = {
    neutral: 'bg-app-surface text-app-hint',
    success: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
    info: 'bg-sky-500/15 text-sky-600 dark:text-sky-400',
    warning: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
  }
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <label className="flex min-h-12 cursor-pointer items-center justify-between gap-3 py-1">
      <span className="text-[15px]">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative h-7 w-12 shrink-0 rounded-full transition-colors disabled:opacity-50 ${checked ? 'bg-app-button' : 'bg-app-hint/40'}`}
      >
        <span
          className={`absolute left-0 top-0.5 size-6 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5.5' : 'translate-x-0.5'}`}
        />
      </button>
    </label>
  )
}
