import { useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'

export function Button({
  variant = 'primary',
  loading = false,
  className = '',
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  const styles: Record<Variant, string> = {
    primary: 'bg-app-button text-app-button-text hover:opacity-90',
    secondary: 'border border-app-border bg-app-bg text-app-text hover:bg-app-surface',
    danger: 'bg-app-danger text-white hover:opacity-90',
    ghost: 'text-app-link hover:bg-app-surface',
  }
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={`inline-flex min-h-9 items-center justify-center gap-2 rounded-lg px-3.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
      {...rest}
    >
      {loading && <span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  )
}

type Tone = 'neutral' | 'success' | 'info' | 'warning' | 'danger'

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  const tones: Record<Tone, string> = {
    neutral: 'bg-app-surface text-app-hint',
    success: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
    info: 'bg-sky-500/15 text-sky-700 dark:text-sky-400',
    warning: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
    danger: 'bg-red-500/15 text-red-700 dark:text-red-400',
  }
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-app-border bg-app-bg ${className}`}>{children}</section>
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-app-hint">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  )
}

/** A row of tabs for a page that gathers two related sections under one menu entry. */
export function SectionTabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: T; label: string }[]
  active: T
  onChange: (key: T) => void
}) {
  return (
    <div className="flex flex-wrap gap-2 border-b border-app-border pb-3">
      {tabs.map((tab) => (
        <Button key={tab.key} variant={active === tab.key ? 'primary' : 'secondary'} onClick={() => onChange(tab.key)}>
          {tab.label}
        </Button>
      ))}
    </div>
  )
}

const fieldClass =
  'w-full rounded-lg border border-app-border bg-app-bg px-3 py-2 text-sm outline-none focus:border-app-button focus:ring-2 focus:ring-app-button/20'

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-app-hint">{hint}</span>}
    </label>
  )
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${fieldClass} ${props.className ?? ''}`} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${fieldClass} ${props.className ?? ''}`} />
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={4} {...props} className={`${fieldClass} ${props.className ?? ''}`} />
}

export function InlineError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-app-danger">
      {message}
    </p>
  )
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  wide = false,
}: {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:items-center">
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} rounded-xl bg-app-bg shadow-xl`}
      >
        <div className="flex items-center justify-between border-b border-app-border px-5 py-3">
          <h2 className="font-semibold">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Yopish" className="text-xl leading-none text-app-hint hover:text-app-text">
            ×
          </button>
        </div>
        <div className="flex max-h-[70vh] flex-col gap-4 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-app-border px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number
  limit: number
  offset: number
  onChange: (offset: number) => void
}) {
  if (total <= limit) return null
  const page = Math.floor(offset / limit) + 1
  const pages = Math.ceil(total / limit)
  return (
    <div className="flex items-center justify-between gap-2 px-4 py-3 text-sm text-app-hint">
      <span>
        Jami: {total} · {page}/{pages}-sahifa
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onChange(offset - limit)}>
          ← Oldingi
        </Button>
        <Button variant="secondary" disabled={page >= pages} onClick={() => onChange(offset + limit)}>
          Keyingi →
        </Button>
      </div>
    </div>
  )
}

export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-app-border text-xs uppercase tracking-wide text-app-hint">
          <tr>
            {head.map((cell, index) => (
              <th key={index} className="whitespace-nowrap px-4 py-2.5 font-medium">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-app-border">{children}</tbody>
      </table>
    </div>
  )
}

export function EmptyRow({ colSpan, text }: { colSpan: number; text: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-10 text-center text-app-hint">
        {text}
      </td>
    </tr>
  )
}
