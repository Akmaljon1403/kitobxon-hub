import { useCallback, useEffect, useState } from 'react'

import { useFeature } from '../components/FeatureGate'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { SavedQuote } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate } from '../utils/router'
import { confirmAction, haptic } from '../utils/telegram'

/** A saved quote: the card picture (preview), sent to the bot chat to share, and removal. */
export function QuoteCard({ quote, onChange }: { quote: SavedQuote; onChange: () => void }) {
  const { api, download } = useAuth()
  const community = useFeature('community')
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

  async function share() {
    setBusy('share')
    setNotice(null)
    try {
      await api('/api/v1/community/from-box', { method: 'POST', body: { saved_quote_id: quote.id } })
      haptic('success')
      setNotice({ text: '🌍 «A‘zolar fikrlari»ga yuborildi — admin ko‘rib chiqqach lentada chiqadi.' })
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
      <blockquote className="whitespace-pre-line text-[15px] italic leading-relaxed">«{quote.text}»</blockquote>
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
      {!quote.book_quote_id && community !== 'off' && (
        <Button variant="ghost" className="text-sm" loading={busy === 'share'} onClick={() => void share()}>
          🌍 Hamma bilan ulashish («A‘zolar fikrlari»)
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
  const [text, setText] = useState('')
  const [source, setSource] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(search.trim()), 350)
    return () => window.clearTimeout(timer)
  }, [search])

  async function add() {
    setBusy(true)
    setError(null)
    try {
      await api('/api/v1/me/quotes', { method: 'POST', body: { text, source: source.trim() || null } })
      haptic('success')
      setText('')
      setSource('')
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Saqlab bo‘lmadi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="px-1">
        <h1 className="text-xl font-semibold">💬 Iqtiboslar sandig‘i</h1>
        <p className="text-sm text-app-hint">Yoqqan jumlalaringiz — izoh bilan, chiroyli kartochka qilib ulashing</p>
      </div>
      <Card className="flex flex-col gap-2">
        <textarea
          rows={3}
          maxLength={1000}
          placeholder="Yangi iqtibos…"
          value={text}
          onChange={(event) => setText(event.target.value)}
          className="rounded-xl bg-app-surface px-3 py-2 text-[15px] italic outline-none"
        />
        <input
          placeholder="Kimniki yoki qaysi kitobdan (ixtiyoriy)"
          value={source}
          maxLength={200}
          onChange={(event) => setSource(event.target.value)}
          className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
        />
        {error && <p className="text-sm text-app-danger">{error}</p>}
        <Button loading={busy} disabled={!text.trim()} onClick={() => void add()}>
          💾 Saqlash
        </Button>
        <p className="text-xs text-app-hint">Kitob sahifasidagi iqtibosni «💾 Saqlash» bilan, javondagi kitobga esa uning sahifasidan qo‘shasiz.</p>
      </Card>
      <input
        placeholder="🔎 Qidirish"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className="rounded-xl bg-app-bg px-3 py-2 text-[15px] outline-none"
      />
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.length === 0 && (
        <Card>
          <EmptyState icon="💬" title={query ? 'Hech narsa topilmadi' : 'Sandiq hozircha bo‘sh'} />
        </Card>
      )}
      {state.status === 'success' && state.data.map((quote) => <QuoteCard key={quote.id} quote={quote} onChange={reload} />)}
    </div>
  )
}
