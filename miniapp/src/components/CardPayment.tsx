import { useRef, useState } from 'react'

import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { CardPayment } from '../types/api'
import { formatDate } from '../utils/format'
import { haptic } from '../utils/telegram'
import { Button, Card } from './ui'

export function formatUzs(amount: number): string {
  return `${amount.toLocaleString('ru-RU').replace(/,/g, ' ')} so'm`
}

const STATUS: Record<CardPayment['status'], string> = {
  PENDING: '⏳ Tekshirilmoqda',
  APPROVED: '✅ Tasdiqlandi',
  REJECTED: '❌ Rad etildi',
}

function itemTitle(item: CardPayment): string {
  if (item.kind === 'STARS') return `⭐ ${item.stars} Stars`
  return item.plan_title ? `💎 ${item.plan_title}` : '❤️ Hissa'
}

function itemStatus(item: CardPayment): string {
  if (item.kind === 'STARS' && item.status === 'APPROVED') return item.delivered_at ? '⭐ Yuborildi' : '✅ Tasdiqlandi, yuborilmoqda'
  return STATUS[item.status]
}

export const PENDING_TEXT =
  "⏳ Chekingiz administratorga tekshirish uchun yuborildi. Odatda bir kun ichida ko'rib chiqiladi — natijasini botda xabar qilamiz."

/** The club's card number with a copy button. */
export function CardNumber({ card, label }: { card: { number: string; holder: string }; label?: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(card.number.replace(/\s/g, ''))
      haptic('success')
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // the clipboard is not available in every webview; the number is still visible
    }
  }

  return (
    <div className="flex flex-col gap-1 rounded-xl bg-app-surface p-3">
      {label && <span className="text-xs text-app-hint">{label}</span>}
      <button type="button" onClick={() => void copy()} className="flex items-center justify-between gap-2 text-left">
        <span className="font-mono text-lg tracking-wider">{card.number}</span>
        <span className="shrink-0 text-sm text-app-link">{copied ? '✓ Nusxalandi' : '📋 Nusxa'}</span>
      </button>
      {card.holder && <span className="text-sm text-app-hint">Egasi: {card.holder}</span>}
    </div>
  )
}

/**
 * Paying one chosen thing to the club's card: transfer the price, then send the receipt.
 * Premium switches on after the super admin confirms; Stars are gifted to the member in Telegram.
 */
export function CardCheckout({
  card,
  price,
  what,
  form,
  onDone,
}: {
  card: { number: string; holder: string }
  price: number
  what: string
  /** The fields that say what is paid for (plan_id or stars). */
  form: Record<string, string>
  onDone: () => void
}) {
  const { upload } = useAuth()
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  async function send(file: File) {
    setBusy(true)
    setNotice(null)
    try {
      const body = new FormData()
      body.append('file', file)
      for (const [key, value] of Object.entries(form)) body.append(key, value)
      await upload('/api/v1/me/premium/card-payments', body, 'POST')
      haptic('success')
      setNotice({ text: PENDING_TEXT })
      onDone()
    } catch (error) {
      haptic('error')
      setNotice({ text: error instanceof ApiError ? error.message : "Chekni yuborib bo'lmadi.", error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <CardNumber card={card} label={`1) ${what}: ${formatUzs(price)} ni shu kartaga o'tkazing (Click, Payme yoki bank ilovasi)`} />
      <Button loading={busy} disabled={busy} onClick={() => fileInput.current?.click()}>
        🧾 2) To'lov chekini (skrinshot) yuborish
      </Button>
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        className="hidden"
        aria-label="To'lov cheki"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) void send(file)
          e.target.value = ''
        }}
      />
      {notice && (
        <p role={notice.error ? 'alert' : 'status'} className={`rounded-xl px-3 py-2 text-sm ${notice.error ? 'text-app-danger' : 'bg-brand-500/10 text-app-text'}`}>
          {notice.text}
        </p>
      )}
    </div>
  )
}

/** «Mening to'lovlarim»: the member's card payments and where each one is. */
export function MyCardPayments({ version }: { version: number }) {
  const { api } = useAuth()
  const history = useAsync((signal) => api<CardPayment[]>('/api/v1/me/premium/card-payments', { signal }), [version])
  if (history.state.status !== 'success' || history.state.data.length === 0) return null
  const waiting = history.state.data.some((item) => item.status === 'PENDING')
  return (
    <Card className="flex flex-col gap-1 text-sm">
      <span className="text-xs font-medium text-app-hint">Mening to'lovlarim</span>
      {waiting && <p className="text-xs text-app-hint">{PENDING_TEXT}</p>}
      {history.state.data.map((item) => (
        <div key={item.id} className="flex flex-col">
          <span className="flex justify-between gap-2">
            <span>
              {itemTitle(item)} · {formatUzs(item.amount_uzs)}
            </span>
            <span className="shrink-0">{itemStatus(item)}</span>
          </span>
          <span className="text-xs text-app-hint">
            {formatDate(item.created_at)}
            {item.reject_reason && ` · ${item.reject_reason}`}
          </span>
        </div>
      ))}
    </Card>
  )
}
