import type { ButtonHTMLAttributes, ReactNode } from 'react'

/* ------------------------------------------------------------------ surfaces */

export function Card({
  children,
  className = '',
  interactive = false,
  tone = 'plain',
}: {
  children: ReactNode
  className?: string
  /** Adds a press animation + pointer affordance for a whole card used as a button. */
  interactive?: boolean
  /** 'brand' gives the card a soft brand tint and border (for highlighted panels). */
  tone?: 'plain' | 'brand'
}) {
  const base =
    tone === 'brand'
      ? 'bg-[color:var(--brand-tint)] border-[color:var(--brand-border)]'
      : 'bg-app-bg border-[color:var(--hairline)]'
  const press = interactive ? 'transition-transform active:scale-[0.985]' : ''
  return (
    <section className={`rounded-2xl border p-4 shadow-[var(--shadow-card)] ${base} ${press} ${className}`}>
      {children}
    </section>
  )
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-2 px-1 pb-1.5 pt-1">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-app-hint">{children}</h2>
      {action}
    </div>
  )
}

/* ------------------------------------------------------------------ buttons */

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

export function Button({
  variant = 'primary',
  loading = false,
  size = 'md',
  className = '',
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; size?: 'sm' | 'md' }) {
  const styles: Record<Variant, string> = {
    primary: 'bg-brand-gradient text-white shadow-[var(--shadow-brand)]',
    secondary: 'bg-app-surface text-app-text',
    ghost: 'bg-transparent text-app-link',
    danger: 'bg-app-danger/12 text-app-danger',
  }
  const sizing = size === 'sm' ? 'min-h-9 px-3 text-sm' : 'min-h-11 px-4 text-[15px]'
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={`inline-flex w-full items-center justify-center gap-2 rounded-xl font-semibold transition-[transform,opacity] active:scale-[0.97] active:opacity-90 disabled:opacity-50 disabled:active:scale-100 ${sizing} ${styles[variant]} ${className}`}
      {...rest}
    >
      {loading && <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  )
}

/* ------------------------------------------------------------------ badges / chips */

type Tone = 'neutral' | 'success' | 'info' | 'warning' | 'brand' | 'gold' | 'danger'

const TONES: Record<Tone, string> = {
  neutral: 'bg-app-surface text-app-hint',
  success: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
  info: 'bg-sky-500/15 text-sky-600 dark:text-sky-400',
  warning: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
  brand: 'bg-brand-500/15 text-brand-600 dark:text-brand-300',
  gold: 'bg-gold-400/20 text-gold-500 dark:text-gold-300',
  danger: 'bg-app-danger/15 text-app-danger',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}>
      {children}
    </span>
  )
}

/** A round emoji/icon holder used at the left of cards and rows. */
export function IconBadge({ children, tone = 'brand', className = '' }: { children: ReactNode; tone?: Tone; className?: string }) {
  return (
    <span
      aria-hidden
      className={`grid size-11 shrink-0 place-items-center rounded-xl text-xl ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

/* ------------------------------------------------------------------ progress */

export function Progress({ value, max = 100, tone = 'brand' }: { value: number; max?: number; tone?: 'brand' | 'gold' }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, Math.round((value / max) * 100))) : 0
  const fill = tone === 'gold' ? 'bg-gold-400' : 'bg-brand-gradient'
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-app-surface" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className={`h-full rounded-full ${fill} transition-[width] duration-500`} style={{ width: `${pct}%` }} />
    </div>
  )
}

/** A compact SVG ring, e.g. for a points/score hero. `value`/`max` set the arc; children go in the middle. */
export function ProgressRing({
  value,
  max = 100,
  size = 72,
  stroke = 7,
  children,
}: {
  value: number
  max?: number
  size?: number
  stroke?: number
  children?: ReactNode
}) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--app-bg-secondary)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--brand-500)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          style={{ transition: 'stroke-dashoffset 0.6s cubic-bezier(0.22,1,0.36,1)' }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center leading-none">{children}</div>
    </div>
  )
}

/* ------------------------------------------------------------------ misc */

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-app-surface px-3 py-2.5 text-center">
      <span className="text-lg font-bold tabular-nums leading-none">{value}</span>
      <span className="text-[11px] text-app-hint">{label}</span>
      {hint && <span className="text-[11px] text-app-hint">{hint}</span>}
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} />
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
        className={`relative h-7 w-12 shrink-0 rounded-full transition-colors disabled:opacity-50 ${checked ? 'bg-brand-500' : 'bg-app-hint/40'}`}
      >
        <span
          className={`absolute left-0 top-0.5 size-6 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5.5' : 'translate-x-0.5'}`}
        />
      </button>
    </label>
  )
}
