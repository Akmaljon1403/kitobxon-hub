import { useCallback, useEffect, useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, Toggle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { CommunityOptions, Contribution, ContributionKind } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate, routeQuery } from '../utils/router'
import { confirmAction, haptic } from '../utils/telegram'

type Tab = 'feed' | 'top' | 'mine'

/** «…» around the words, unless they already begin with a quote mark. */
function quoted(text: string): string {
  return /^[«"“„']/.test(text.trim()) ? text : `«${text}»`
}

const KIND_FILTERS: { value: ContributionKind | ''; label: string }[] = [
  { value: '', label: 'Hammasi' },
  { value: 'QUOTE', label: '📖 Iqtiboslar' },
  { value: 'THOUGHT', label: '💡 Fikrlar' },
  { value: 'BOOK', label: '📚 Kitoblar' },
  { value: 'EVENT', label: '📅 Tadbirlar' },
  { value: 'CLUB', label: "🌟 E'tiroflar" },
]

const STATUS: Record<Contribution['status'], { text: string; tone: 'warning' | 'success' | 'neutral' }> = {
  PENDING: { text: '⏳ Ko‘rib chiqilmoqda', tone: 'warning' },
  APPROVED: { text: '✅ Lentada', tone: 'success' },
  HIDDEN: { text: '🙈 Yashirilgan', tone: 'neutral' },
}

/** One text in the feed: the words, its source and author, ❤️, and its card. */
function ContributionCard({ item, mine = false, onChange }: { item: Contribution; mine?: boolean; onChange: () => void }) {
  const { api, download } = useAuth()
  const [liked, setLiked] = useState(item.liked)
  const [likes, setLikes] = useState(item.likes)
  const [preview, setPreview] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview)
  }, [preview])

  async function toggleLike() {
    try {
      const result = await api<{ liked: boolean; likes: number }>(`/api/v1/community/${item.id}/like`, { method: 'POST' })
      setLiked(result.liked)
      setLikes(result.likes)
    } catch (err) {
      setNotice({ text: err instanceof ApiError ? err.message : 'Bo‘lmadi', error: true })
    }
  }

  async function showCard() {
    if (preview) {
      setPreview(null)
      return
    }
    setBusy('card')
    try {
      setPreview(URL.createObjectURL(await download(`/api/v1/community/${item.id}/card.png`)))
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
      await api(`/api/v1/community/${item.id}/send`, { method: 'POST' })
      haptic('success')
      setNotice({ text: '✅ Kartochka bot chatiga yuborildi — u yerdan do‘stlaringizga ulashing.' })
    } catch (err) {
      setNotice({ text: err instanceof ApiError ? err.message : 'Yuborib bo‘lmadi', error: true })
    } finally {
      setBusy(null)
    }
  }

  async function remove() {
    if (!(await confirmAction('Lentadan olib tashlansinmi? (Iqtiboslar sandig‘ingizda qoladi)'))) return
    await api(`/api/v1/community/${item.id}`, { method: 'DELETE' })
    onChange()
  }

  return (
    <Card className={`flex flex-col gap-2 ${item.featured ? 'ring-2 ring-amber-400/70' : ''}`}>
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-app-hint">
        <span>{item.kind_title}</span>
        {item.featured && <Badge tone="warning">⭐ Tanlangan</Badge>}
        {item.in_channel && <Badge tone="info">📣 Kanalda</Badge>}
        {mine && <Badge tone={STATUS[item.status].tone}>{STATUS[item.status].text}</Badge>}
      </div>
      <blockquote className="whitespace-pre-line text-[15px] italic leading-relaxed">{quoted(item.text)}</blockquote>
      {item.source && <p className="text-right text-sm text-app-hint">— {item.source}</p>}
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="text-app-hint">
          ✍️ {item.author} · {formatDate(item.created_at)}
        </span>
        {item.status === 'APPROVED' && (
          <button type="button" onClick={() => void toggleLike()} className="flex items-center gap-1 rounded-full bg-app-surface px-3 py-1">
            <span>{liked ? '❤️' : '🤍'}</span>
            <span className="tabular-nums">{likes}</span>
          </button>
        )}
      </div>
      {preview && <img src={preview} alt="Kartochka" className="w-full rounded-xl" />}
      {notice && <p className={`text-sm ${notice.error ? 'text-app-danger' : 'text-app-link'}`}>{notice.text}</p>}
      <div className={`grid gap-2 ${mine ? 'grid-cols-3' : 'grid-cols-2'}`}>
        <Button variant="secondary" className="px-2 text-sm" loading={busy === 'card'} onClick={() => void showCard()}>
          {preview ? 'Yopish' : '🖼 Kartochka'}
        </Button>
        <Button variant="secondary" className="px-2 text-sm" loading={busy === 'send'} onClick={() => void send()}>
          📤 Ulashish
        </Button>
        {mine && (
          <Button variant="ghost" className="px-2 text-sm" onClick={() => void remove()}>
            🗑
          </Button>
        )}
      </div>
    </Card>
  )
}

/** «💬 A'zolar fikrlari»: what members wrote — quotes, thoughts, impressions, testimonials. */
export function CommunityPage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/'), [])
  useBackButton(goBack)
  const [tab, setTab] = useState<Tab>('feed')
  const [kind, setKind] = useState<ContributionKind | ''>('')
  const { state, reload } = useAsync((signal) => {
    if (tab === 'mine') return api<Contribution[]>('/api/v1/community/mine', { signal })
    const params = new URLSearchParams({ sort: tab === 'top' ? 'top' : 'new' })
    if (kind) params.set('kind', kind)
    return api<Contribution[]>(`/api/v1/community?${params.toString()}`, { signal })
  }, [tab, kind])

  return (
    <div className="flex flex-col gap-3">
      <div className="px-1">
        <h1 className="text-xl font-semibold">💬 A‘zolar fikrlari</h1>
        <p className="text-sm text-app-hint">
          Kitobxonlarimizning iqtiboslari, fikrlari va taassurotlari. Eng yaxshilari klub kanalida chiroyli kartochka bo‘lib chiqadi.
        </p>
      </div>
      <Button onClick={() => navigate('/community/new')}>✍️ Yozish</Button>
      <div className="grid grid-cols-3 gap-1 rounded-xl bg-app-surface p-1">
        {(
          [
            ['feed', 'Yangi'],
            ['top', '❤️ Eng yoqqan'],
            ['mine', 'Meniki'],
          ] as [Tab, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            className={`rounded-lg py-1.5 text-sm ${tab === value ? 'bg-app-bg font-semibold shadow-sm' : 'text-app-hint'}`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab !== 'mine' && (
        <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
          {KIND_FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setKind(item.value)}
              className={`shrink-0 rounded-full px-3 py-1 text-sm ${kind === item.value ? 'bg-app-button text-app-button-text' : 'bg-app-bg text-app-hint'}`}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.length === 0 && (
        <Card>
          <EmptyState icon="💬" title={tab === 'mine' ? 'Hali hech narsa yozmagansiz' : 'Lenta hozircha bo‘sh'}>
            Birinchi bo‘lib yozing — yoqqan iqtibosingiz yoki fikringiz boshqalarni ilhomlantiradi.
          </EmptyState>
        </Card>
      )}
      {state.status === 'success' &&
        state.data.map((item) => <ContributionCard key={item.id} item={item} mine={tab === 'mine'} onChange={reload} />)}
    </div>
  )
}

const PLACEHOLDERS: Record<ContributionKind, string> = {
  QUOTE: 'Kitobdagi yoqqan jumla…',
  THOUGHT: 'O‘z fikringiz yoki hikmatingiz…',
  BOOK: 'Kitob sizga nima berdi? Nimasi yoqdi?',
  EVENT: 'Tadbirda nima yoqdi? Nimani o‘rgandingiz?',
  CLUB: 'Klub sizga nima berdi?',
}

/** Write a quote, a thought, an impression or a testimonial; choose the card design. */
export function CommunityNewPage() {
  const { api, download } = useAuth()
  const goBack = useCallback(() => navigate('/community'), [])
  useBackButton(goBack)
  const query = routeQuery()
  const initialKind = (query.get('kind') as ContributionKind | null) ?? 'QUOTE'
  const { state } = useAsync((signal) => api<CommunityOptions>('/api/v1/community/options', { signal }), [])
  const [kind, setKind] = useState<ContributionKind>(initialKind)
  const [text, setText] = useState('')
  const [author, setAuthor] = useState('')
  const [bookId, setBookId] = useState(query.get('book') ?? '')
  const [eventId, setEventId] = useState(query.get('event') ?? '')
  const [style, setStyle] = useState('classic')
  const [showName, setShowName] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState<Contribution | null>(null)
  const [preview, setPreview] = useState<string | null>(null)

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview)
  }, [preview])

  async function loadPreview(item: Contribution, look: string) {
    try {
      const blob = await download(`/api/v1/community/${item.id}/card.png?style=${look}`)
      setPreview(URL.createObjectURL(blob))
    } catch {
      setPreview(null)
    }
  }

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const item = await api<Contribution>('/api/v1/community', {
        method: 'POST',
        body: {
          kind,
          text: text.trim(),
          source: kind === 'QUOTE' && author.trim() ? author.trim() : null,
          book_id: (kind === 'QUOTE' || kind === 'BOOK') && bookId ? bookId : null,
          event_id: kind === 'EVENT' && eventId ? eventId : null,
          show_name: showName,
          style,
        },
      })
      haptic('success')
      setSent(item)
      void loadPreview(item, style)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Yuborib bo‘lmadi')
    } finally {
      setBusy(false)
    }
  }

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} />
  const options = state.data

  if (sent) {
    return (
      <div className="flex flex-col gap-3">
        <Card className="flex flex-col gap-2 text-center">
          <span className="text-4xl">🌟</span>
          <h1 className="text-lg font-semibold">Rahmat!</h1>
          <p className="text-sm text-app-hint">
            {sent.status === 'APPROVED'
              ? 'Lentaga qo‘shildi — boshqa kitobxonlar o‘qiydi va ❤️ bosadi.'
              : 'Admin ko‘rib chiqqach lentada chiqadi va sizga xabar beramiz. Eng yaxshilari klub kanalida e’lon qilinadi.'}
          </p>
        </Card>
        {preview && <img src={preview} alt="Kartochka" className="w-full rounded-2xl shadow-sm" />}
        <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
          {options.styles.map((item) => (
            <button
              key={item.code}
              type="button"
              onClick={() => void loadPreview(sent, item.code)}
              className="shrink-0 rounded-full bg-app-bg px-3 py-1 text-sm text-app-hint"
            >
              {item.title}
            </button>
          ))}
        </div>
        <Button
          variant="secondary"
          onClick={() => void api(`/api/v1/community/${sent.id}/send`, { method: 'POST' }).then(() => haptic('success'))}
        >
          📤 Kartochkani bot chatiga yuborish
        </Button>
        <Button
          onClick={() => {
            setSent(null)
            setText('')
            setAuthor('')
          }}
        >
          ✍️ Yana yozish
        </Button>
        <Button variant="ghost" onClick={() => navigate('/community')}>
          💬 Lentaga qaytish
        </Button>
      </div>
    )
  }

  const tooShort = text.trim().length < 8
  return (
    <div className="flex flex-col gap-3">
      <div className="px-1">
        <h1 className="text-xl font-semibold">✍️ Fikr yozish</h1>
        <p className="text-sm text-app-hint">Iqtibos va fikrlaringiz «Iqtiboslar sandig‘i»ngizda ham saqlanadi.</p>
      </div>
      <Card className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-1.5">
          {options.kinds.map((item) => (
            <button
              key={item.code}
              type="button"
              onClick={() => setKind(item.code)}
              className={`rounded-full px-3 py-1 text-sm ${kind === item.code ? 'bg-app-button text-app-button-text' : 'bg-app-surface text-app-hint'}`}
            >
              {item.title}
            </button>
          ))}
        </div>
        <textarea
          rows={5}
          maxLength={1000}
          placeholder={PLACEHOLDERS[kind]}
          value={text}
          onChange={(event) => setText(event.target.value)}
          className="rounded-xl bg-app-surface px-3 py-2 text-[15px] italic outline-none"
        />
        <p className="-mt-2 text-right text-xs text-app-hint">{text.length}/1000</p>
        {kind === 'QUOTE' && (
          <input
            placeholder="Kim aytgan? (masalan: Abdulla Qodiriy)"
            value={author}
            maxLength={200}
            onChange={(event) => setAuthor(event.target.value)}
            className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
          />
        )}
        {(kind === 'QUOTE' || kind === 'BOOK') && (
          <select
            value={bookId}
            onChange={(event) => setBookId(event.target.value)}
            className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
          >
            <option value="">{kind === 'BOOK' ? 'Klub kitobini tanlang (ixtiyoriy)' : 'Klub kitobidan (ixtiyoriy)'}</option>
            {options.books.map((book) => (
              <option key={book.id} value={book.id}>
                {book.title}
                {book.author ? ` — ${book.author}` : ''}
              </option>
            ))}
          </select>
        )}
        {kind === 'EVENT' &&
          (options.events.length ? (
            <select
              value={eventId}
              onChange={(event) => setEventId(event.target.value)}
              className="rounded-xl bg-app-surface px-3 py-2 text-[15px] outline-none"
            >
              <option value="">Qaysi tadbir?</option>
              {options.events.map((event) => (
                <option key={event.id} value={event.id}>
                  {event.title} — {formatDate(event.starts_at)}
                </option>
              ))}
            </select>
          ) : (
            <p className="rounded-xl bg-app-surface px-3 py-2 text-sm text-app-hint">Siz qatnashgan tadbirlar hali yo‘q.</p>
          ))}
        <div className="flex flex-col gap-1.5">
          <p className="text-sm font-medium">🎨 Kartochka dizayni</p>
          <div className="grid grid-cols-2 gap-1.5">
            {options.styles.map((item) => (
              <button
                key={item.code}
                type="button"
                onClick={() => setStyle(item.code)}
                className={`rounded-xl px-2 py-2 text-left text-sm ${style === item.code ? 'bg-app-button text-app-button-text' : 'bg-app-surface'}`}
              >
                {item.title}
              </button>
            ))}
          </div>
        </div>
        <Toggle checked={showName} onChange={setShowName} label="Ismim ko‘rinsin (o‘chirilsa — «Klub a’zosi»)" />
        {error && <p className="text-sm text-app-danger">{error}</p>}
        <Button
          loading={busy}
          disabled={tooShort || (kind === 'EVENT' && !eventId)}
          onClick={() => void submit()}
        >
          📨 Yuborish
        </Button>
        <p className="text-xs text-app-hint">
          Yuborish bilan klub matningizni ilovada, kanalda va a‘zolarga xabarda ishlatishiga rozilik bildirasiz. Qabul qilingan har bir fikr uchun
          ball beriladi.
        </p>
      </Card>
    </div>
  )
}
