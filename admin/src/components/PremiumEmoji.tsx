import { useState } from 'react'

import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import { Button, Card, InlineError } from './ui'

interface EmojiList {
  items: { emoji: string; custom_emoji_id: string; fallback: string; created_at: string }[]
  paused: boolean
  state: 'unknown' | 'working' | 'refused' | 'group_refused'
  checked_at: string | null
}

/** Why Telegram may refuse premium emoji, and what to do (shown when it did). */
function RefusedHelp() {
  return (
    <div className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
      <p className="font-semibold">⚠️ Telegram premium emojini rad etdi — xabarlar hozir oddiy emoji bilan ketyapti.</p>
      <p className="mt-1">
        <b>Sabab:</b> Telegram qoidasiga ko'ra bot premium emojini faqat <b>bot egasida</b> (botni @BotFather'da yaratgan akkauntda)
        Telegram Premium bo'lsa ishlata oladi. Emojilarni kiritgan adminning Premium'i hisobga olinmaydi.
      </p>
      <p className="mt-1">
        <b>Yechim</b> (bittasi yetarli): 1) bot egasi akkauntiga Telegram Premium olish; 2) @BotFather → Bot Settings → Transfer
        Ownership orqali botni Premium'i bor ishonchli adminga o'tkazish; 3) Fragment'da botga qo'shimcha username olish (kanallarda
        ham ishlaydi). Emojilar saqlanib turadi — ruxsat paydo bo'lgach «🧪 Tekshirish»ni bosing.
      </p>
    </div>
  )
}

/** «✨ Premium emojilar»: ordinary emoji in every bot message are replaced by the club's premium ones. */
export function PremiumEmoji() {
  const { api } = useSession()
  const list = useAsync((signal) => api<EmojiList>('/api/v1/admin/custom-emoji', { signal }))
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function remove(emoji: string | null) {
    if (emoji === null && !window.confirm("Barcha premium emojilar o'chirilsinmi? Bot oddiy emojilarga qaytadi.")) return
    setBusy(emoji ?? 'all')
    setError(null)
    try {
      await api(`/api/v1/admin/custom-emoji${emoji ? `?emoji=${encodeURIComponent(emoji)}` : ''}`, { method: 'DELETE' })
      list.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "O'chirib bo'lmadi.")
    } finally {
      setBusy(null)
    }
  }

  async function sample() {
    setBusy('test')
    setError(null)
    setNotice(null)
    try {
      const result = await api<{ sent: boolean; premium_shown: boolean }>('/api/v1/admin/custom-emoji/test', { method: 'POST' })
      setNotice(
        result.premium_shown
          ? "✓ Telegram qabul qildi — namuna bot chatingizga yuborildi, a'zolar premium emojilarni ko'radi."
          : 'Namuna oddiy emoji bilan yuborildi: Telegram premium emojini rad etdi (sababi pastda).',
      )
      list.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi.")
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h2 className="font-semibold">✨ Premium emojilar</h2>
        <p className="text-sm text-app-hint">
          Bot yuboradigan har bir xabardagi oddiy emoji (masalan, «Assalomu alaykum ❤️» dagi ❤️) siz tanlagan premium (animatsion)
          emojiga almashadi. Qo'shish: botga <b>/emoji</b> yozing va premium emojili xabar yuboring (yoki «❤️ = premium❤️» deb
          juftlab yozing), tugatgach <b>/tayyor</b>.
        </p>
        <p className="mt-1 text-xs text-app-hint">
          Telegram qoidasi: premium emoji bot <b>egasida</b> Telegram Premium bo'lsa shaxsiy chat va guruhlarda ishlaydi (kanallarda —
          faqat Fragment username bilan). Ruxsat bo'lmasa bot buni sezadi va xabarni oddiy emoji bilan yuboradi — hech narsa buzilmaydi.
        </p>
      </div>
      {list.state.status === 'success' && (list.state.data.paused || list.state.data.state === 'refused') && <RefusedHelp />}
      {list.state.status === 'success' && list.state.data.state === 'working' && !list.state.data.paused && (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          ✅ Telegram premium emojini qabul qilyapti — a'zolar ularni ko'radi.
        </p>
      )}
      {list.state.status === 'success' && list.state.data.state === 'group_refused' && (
        <p className="rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-900">
          ℹ️ Kanal yoki guruhda Telegram premium emojini rad etdi — u yerda oddiy emojilar ishlatiladi. Shaxsiy xabarlarni tekshirish
          uchun «🧪 Tekshirish»ni bosing.
        </p>
      )}
      {list.state.status === 'success' && (
        <div className="flex flex-wrap gap-2">
          {list.state.data.items.length === 0 && <p className="text-sm text-app-hint">Hali premium emoji saqlanmagan.</p>}
          {list.state.data.items.map((item) => (
            <span key={item.emoji} className="flex items-center gap-1 rounded-full border border-app-border px-3 py-1 text-sm">
              <span className="text-lg">{item.emoji}</span>
              <span className="text-xs text-app-hint" title={item.custom_emoji_id}>
                → premium
              </span>
              <button
                type="button"
                className="ml-1 text-app-hint hover:text-rose-600"
                aria-label={`${item.emoji} ni o'chirish`}
                disabled={busy !== null}
                onClick={() => void remove(item.emoji)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <InlineError message={error} />
      {notice && <p className="text-sm text-emerald-700">{notice}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" loading={busy === 'test'} onClick={() => void sample()}>
          🧪 Tekshirish (o'zimga namuna)
        </Button>
        {list.state.status === 'success' && list.state.data.items.length > 0 && (
          <Button variant="ghost" loading={busy === 'all'} onClick={() => void remove(null)}>
            Hammasini o'chirish
          </Button>
        )}
      </div>
    </Card>
  )
}
