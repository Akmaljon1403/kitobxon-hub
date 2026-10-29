import { useCallback, useEffect, useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, PageTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { QuoteBoxOptions, QuoteVisibility, SavedQuote } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate } from '../utils/router'
import { confirmAction, haptic } from '../utils/telegram'

const SHARED: Record<string, { label: string; tone: 'success' | 'info' | 'neutral' | 'warning' }> = {
  APPROVED: { label: '🌍 Umumiy', tone: 'success' },
  PENDING: { label: '⏳ Umumiyga — ko‘rib chiqilmoqda', tone: 'warning' },
  HIDDEN: { label: '🙈 Admin yashirgan', tone: 'neutral' },
}

/** «🔒 Faqat o‘zim uchun» / «🌍 Umumiy» — chosen before saving, changeable any time. */
export function VisibilityChoice({ value, onChange }: { value: QuoteVisibility; onChange: (value: QuoteVisibility) => void }) {
  const items: { code: QuoteVisibility; title: string; hint: string }[] = [
    { code: 'PERSONAL', title: '🔒 Shaxsiy', hint: 'faqat sizga ko‘rinadi' },
    { code: 'COMMON', title: '🌍 Umumiy', hint: 'hamma ko‘radi, karta bo‘lib ulashiladi' },
  ]
  return (
    <div className="grid grid-cols-2 gap-1.5">
      {items.map((item) => (
        <button
          key={item.code}
          type="button"
          onClick={() => onChange(item.code)}
          className={`rounded-xl px-3 py-2 text-left ${value === item.code ? 'bg-brand-500 text-white' : 'bg-app-surface'}`}
        >
          <span className="block text-sm font-medium">{item.title}</span>
          <span className={`block text-xs ${value === item.code ? 'opacity-80' : 'text-app-hint'}`}>{item.hint}</span>
        </button>
      ))}
    </div>
  )
}

/** A saved quote: the card picture (preview), sent to the bot chat to share, personal/common, and removal. */
export function QuoteCard({
  quote,
  onChange,
  commonAllowed = true,
}: {
  quote: SavedQuote
  onChange: () => void
  commonAllowed?: boolean
}) {
  const { api, download } = useAuth()
  const [preview, setPreview] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview)
  }, [preview])

  async function showCard() {
    if (preview) {
      setPreview(null)
      return
    }
    setBusy('card')
    try {
      setPreview(URL.createObjectURL(await download(`/api/v1/me/quotes/${quote.id}/card.png`)))
    } catch {
      setNotice({ text: 'Kartochkani ochib bo‘lmadi', error: true })
    } finally {
      setBusy(null)
    }
  }

  async function send() {
    setBusy('send')
    setNotice(null)
    try {
      await api(`/api/v1/me/quotes/${quote.id}/send`, { method: 'POST' })
      haptic('success')
      setNotice({ text: '✅ Kartochka bot chatiga yuborildi — u yerdan do‘stlaringizga ulashing.' })
    } catch (err) {
      setNotice({ text: err instanceof ApiError ? err.message : 'Yuborib bo‘lmadi', error: true })
    } finally {
      setBusy(null)
    }
  }

  async function setVisibility(visibility: QuoteVisibility) {
    setBusy('share')
    setNotice(null)
    try {
      const saved = await api<SavedQuote>(`/api/v1/me/quotes/${quote.id}/visibility`, { method: 'POST', body: { visibility } })
      haptic('success')
      setNotice({
        text:
          visibility === 'PERSONAL'
            ? '🔒 Endi faqat o‘zingizga ko‘rinadi.'
            : saved.shared === 'APPROVED'
              ? '🌍 Umumiy lentada — hamma ko‘radi.'
              : '🌍 Umumiyga yuborildi — admin ko‘rib chiqqach lentada chiqadi.',
      })
      onChange()
    } catch (err) {
      setNotice({ text: err instanceof ApiError ? err.message : 'Yuborib bo‘lmadi', error: true })
    } finally {
      setBusy(null)
    }
  }

  async function remove() {
    if (!(await confirmAction('Iqtibos sandiqdan o‘chirilsinmi?'))) return
    await api(`/api/v1/me/quotes/${quote.id}`, { method: 'DELETE' })
    onChange()
  }

  return (
    <Card className="flex flex-col gap-2">
      {!quote.book_quote_id && (
        <div className="flex justify-end">
          {quote.shared ? <Badge tone={SHARED[quote.shared].tone}>{SHARED[quote.shared].label}</Badge> : <Badge>🔒 Shaxsiy</Badge>}
        </div>
      )}
      <blockquote className="whitespace-pre-line font-serif text-[15px] italic leading-relaxed">«{quote.text}»</blockquote>
      <p className="text-right text-sm text-app-hint">
        {quote.source ? `— ${quote.source}` : ''}
        {quote.page ? `, ${quote.page}-bet` : ''}
      </p>
      {quote.note && <p className="rounded-xl bg-app-surface px-3 py-2 text-sm">📝 {quote.note}</p>}
      {preview && <img src={preview} alt="Iqtibos kartochkasi" className="w-full rounded-xl" />}
      {notice && <p className={`text-sm ${notice.error ? 'text-app-danger' : 'text-app-link'}`}>{notice.text}</p>}
      <div className="grid grid-cols-3 gap-2">
        <Button variant="secondary" className="px-2 text-sm" loading={busy === 'card'} onClick={() => void showCard()}>
          {preview ? 'Yopish' : '🖼 Kartochka'}
        </Button>
        <Button variant="secondary" className="px-2 text-sm" loading={busy === 'send'} onClick={() => void send()}>
          📤 Ulashish
        </Button>
        <Button variant="ghost" className="px-2 text-sm" onClick={() => void remove()}>
          🗑
        </Button>
      </div>
      {!quote.book_quote_id && quote.shared && (
        <Button variant="ghost" className="text-sm" loading={busy === 'share'} onClick={() => void setVisibility('PERSONAL')}>
          🔒 Shaxsiyga qaytarish
        </Button>
      )}
      {!quote.book_quote_id && !quote.shared && commonAllowed && (
        <Button variant="ghost" className="text-sm" loading={busy === 'share'} onClick={() => void setVisibility('COMMON')}>
          🌍 Umumiy qilish (hamma ko‘rsin)
        </Button>
      )}
      <p className="text-xs text-app-hint">{formatDate(quote.created_at)}</p>
    </Card>
  )
}

/** «💬 Iqtiboslar sandig'i»: every saved line, searchable; new ones from anywhere. */
export function QuotesPage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/shelf'), [])
  useBackButton(goBack)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const { state, reload } = useAsync(
    (signal) => api<SavedQuote[]>(`/api/v1/me/quotes${query ? `?search=${encodeURIComponent(query)}` : ''}`, { signal }),
    [query],
  )
  const options = useAsync((signal) => api<QuoteBoxOptions>('/api/v1/me/quotes/options', { signal }))
  const [text, setText] = useState('')
  const [source, setSource] = useState('')
  const [visibility, setVisibility] = useState<QuoteVisibility | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const box = options.state.status === 'success' ? options.state.data : null
  const chosen: QuoteVisibility = box?.common_allowed ? (visibility ?? box.default) : 'PERSONAL'

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 350)
    return () => window.clearTimeout(timer)
  }, [search])

  async function add() {
    setBusy(true)
    setError(null)
    try {
      const saved = await api<SavedQuote>('/api/v1/me/quotes', {
        method: 'POST',
        body: { text, source: source.trim() || null, visibility: chosen },
      })
      haptic('success')
      setText('')
      setSource('')
      setNotice(
        saved.shared === 'APPROVED'
          ? '✅ Saqlandi va umumiy lentaga chiqdi 🌍'
          : saved.shared === 'PENDING'
            ? '✅ Saqlandi. Umumiy lentada admin ko‘rib chiqqach chiqadi ⏳'
            : '✅ Saqlandi — faqat sizga ko‘rinadi 🔒',
      )
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Saqlab bo‘lmadi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div>
        <PageTitle icon="quote">Iqtiboslar sandig‘i</PageTitle>
        <p className="px-1 text-sm text-app-hint">Yoqqan jumlalaringiz — izoh bilan, chiroyli kartochka qilib ulashing</p>
      </div>
      <Card className="flex flex-col gap-2">
        <textarea
          rows={3}
          maxLength={1000}
          placeholder="Yangi iqtibos…"
          value={text}
          onChange={(event) => setText(event.target.value)}
          className="rounded-xl bg-app-surface px-3 py-2 text-[15px] italic outline-none transition focus:ring-2 focus:ring-brand-400/50"
        />
        <input
          placeholder="Kimniki yoki qaysi kitobdan (ixtiyoriy)"
          value={source}
          maxLength={200}
          onChange={(event) => setSource(event.target.value)}
          className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none transition focus:ring-2 focus:ring-brand-400/50"
        />
        {box?.common_allowed && (
          <>
            <p className="text-sm font-medium">Kim ko‘radi?</p>
            <VisibilityChoice value={chosen} onChange={setVisibility} />
            {chosen === 'COMMON' && !box.auto_publish && (
              <p className="text-xs text-app-hint">Umumiy iqtiboslar «A‘zolar fikrlari» lentasida admin ko‘rib chiqqach chiqadi.</p>
            )}
          </>
        )}
        {error && <p className="text-sm text-app-danger">{error}</p>}
        {notice && <p className="text-sm text-app-link">{notice}</p>}
        <Button loading={busy} disabled={!text.trim()} onClick={() => void add()}>
          💾 Saqlash
        </Button>
        <p className="text-xs text-app-hint">Kitob sahifasidagi iqtibosni «💾 Saqlash» bilan, javondagi kitobga esa uning sahifasidan qo‘shasiz.</p>
      </Card>
      <input
        placeholder="🔎 Qidirish"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className="rounded-xl bg-app-bg px-3 py-2 text-[15px] outline-none transition focus:ring-2 focus:ring-brand-400/50"
      />
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.length === 0 && (
        <Card>
          <EmptyState icon="quote" title={query ? 'Hech narsa topilmadi' : 'Sandiq hozircha bo‘sh'} />
        </Card>
      )}
      {state.status === 'success' && state.data.map((quote) => (
          <QuoteCard key={quote.id} quote={quote} onChange={reload} commonAllowed={box?.common_allowed ?? false} />
        ))}
    </div>
  )
}
