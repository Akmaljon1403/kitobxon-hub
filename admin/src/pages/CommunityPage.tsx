import { useEffect, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, Field, InlineError, Input, Modal, PageHeader, Select, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError, saveBlob } from '../services/api'
import { useSession } from '../store/session'
import type { Faculty } from '../types/api'
import { formatDate, formatDateTime, fromLocalInput } from '../utils/format'

type Status = 'PENDING' | 'APPROVED' | 'FEATURED' | 'HIDDEN'

/** «…» around the words, unless they already begin with a quote mark. */
function quoted(text: string): string {
  return /^[«"“„']/.test(text.trim()) ? text : `«${text}»`
}

interface Item {
  id: string
  kind: string
  kind_title: string
  text: string
  source: string | null
  author: string
  show_name: boolean
  style: string
  status: 'PENDING' | 'APPROVED' | 'HIDDEN'
  featured: boolean
  likes: number
  created_at: string
  member: string
  member_details: string
  uses: { where: string; title: string; at: string; by: string }[]
}

interface Listing {
  counts: Record<Status, number>
  items: Item[]
  styles: { code: string; title: string }[]
  kinds: { code: string; title: string }[]
  next_quote_day: string
}

const TABS: { value: Status; label: string }[] = [
  { value: 'PENDING', label: '⏳ Yangi' },
  { value: 'APPROVED', label: '✅ Lentada' },
  { value: 'FEATURED', label: '⭐ Tanlangan' },
  { value: 'HIDDEN', label: '🙈 Yashirilgan' },
]

type Action = 'card' | 'channel' | 'members' | 'quote' | 'edit'

/** The card in the chosen design: preview, download, and the place it goes to. */
function UseDialog({
  item,
  action,
  listing,
  onClose,
  onDone,
}: {
  item: Item
  action: Action
  listing: Listing
  onClose: () => void
  onDone: (message: string) => void
}) {
  const { api, download, can } = useSession()
  const [style, setStyle] = useState(item.style)
  const [preview, setPreview] = useState<string | null>(null)
  const [caption, setCaption] = useState('')
  const [later, setLater] = useState('')
  const [facultyId, setFacultyId] = useState('')
  const [course, setCourse] = useState('')
  const [group, setGroup] = useState('')
  const [day, setDay] = useState(listing.next_quote_day)
  const [text, setText] = useState(item.text)
  const [source, setSource] = useState(item.source ?? '')
  const [count, setCount] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const faculties = useAsync((signal) => api<Faculty[]>('/api/v1/admin/faculties', { signal }), [])

  useEffect(() => {
    if (action === 'edit' || action === 'quote') return
    let url: string | null = null
    let stopped = false
    download(`/api/v1/admin/community/${item.id}/card.png?style=${style}`)
      .then((blob) => {
        if (stopped) return
        url = URL.createObjectURL(blob)
        setPreview(url)
      })
      .catch(() => setPreview(null))
    return () => {
      stopped = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [action, download, item.id, style])

  const audience = {
    faculty_id: facultyId || null,
    course: course ? Number(course) : null,
    group_name: group.trim() || null,
  }

  useEffect(() => {
    if (action !== 'members') return
    setCount(null)
    api<{ recipients: number }>(`/api/v1/admin/community/${item.id}/members`, {
      method: 'POST',
      body: { ...audience, dry_run: true },
    })
      .then((result) => setCount(result.recipients))
      .catch(() => setCount(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, facultyId, course, group])

  async function run() {
    setBusy(true)
    setError(null)
    try {
      if (action === 'channel') {
        const result = await api<{ scheduled_at: string }>(`/api/v1/admin/community/${item.id}/channel`, {
          method: 'POST',
          body: { style, caption: caption.trim() || null, scheduled_at: fromLocalInput(later) },
        })
        onDone(later ? `📣 Kanalga rejalashtirildi: ${formatDateTime(result.scheduled_at)}` : '📣 Kanalga yuborildi')
      } else if (action === 'members') {
        const result = await api<{ recipients: number }>(`/api/v1/admin/community/${item.id}/members`, {
          method: 'POST',
          body: { style, caption: caption.trim() || null, ...audience },
        })
        onDone(`📢 ${result.recipients} nafar a'zoga yuborilmoqda`)
      } else if (action === 'quote') {
        const result = await api<{ day: string }>(`/api/v1/admin/community/${item.id}/quote-of-day`, {
          method: 'POST',
          body: { day: day || null },
        })
        onDone(`📜 Kun iqtibosi: ${formatDate(result.day)}`)
      } else if (action === 'edit') {
        await api(`/api/v1/admin/community/${item.id}`, { method: 'PATCH', body: { text, source: source.trim() || null } })
        onDone('✏️ Saqlandi')
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bajarib bo‘lmadi')
    } finally {
      setBusy(false)
    }
  }

  const titles: Record<Action, string> = {
    card: '🖼 Kartochka',
    channel: '📣 Kanalga joylash',
    members: "📢 A'zolarga yuborish",
    quote: '📜 Kun iqtibosi qilish',
    edit: '✏️ Matnni tuzatish',
  }
  const sending = action === 'channel' || action === 'members'

  return (
    <Modal
      title={titles[action]}
      onClose={onClose}
      wide={action !== 'edit' && action !== 'quote'}
      footer={
        <>
          {action === 'card' && (
            <Button
              variant="secondary"
              onClick={() => void download(`/api/v1/admin/community/${item.id}/card.png?style=${style}`).then((blob) => saveBlob(blob, `kartochka-${item.id.slice(0, 8)}.png`))}
            >
              📥 Yuklab olish
            </Button>
          )}
          {action === 'card' && (
            <Button
              loading={busy}
              onClick={() => {
                setBusy(true)
                api(`/api/v1/admin/community/${item.id}/me`, { method: 'POST', body: { style } })
                  .then(() => onDone('📨 Kartochka bot chatingizga yuborildi — u yerdan istalgan joyga uzating'))
                  .catch((err) => setError(err instanceof ApiError ? err.message : 'Yuborib bo‘lmadi'))
                  .finally(() => setBusy(false))
              }}
            >
              📨 Menga yuborish (botda)
            </Button>
          )}
          {action !== 'card' && (
            <Button loading={busy} disabled={sending && !can('NOTIFICATION_SEND')} onClick={() => void run()}>
              {action === 'members' ? `Yuborish${count !== null ? ` (${count} nafar)` : ''}` : 'Tasdiqlash'}
            </Button>
          )}
        </>
      }
    >
      {action === 'edit' ? (
        <>
          <Field label="Matn">
            <Textarea rows={6} value={text} maxLength={1000} onChange={(event) => setText(event.target.value)} />
          </Field>
          <Field label="Manba (muallif — kitob)">
            <Input value={source} maxLength={255} onChange={(event) => setSource(event.target.value)} />
          </Field>
        </>
      ) : action === 'quote' ? (
        <>
          <p className="text-sm text-app-hint">
            Matn klub iqtiboslariga qo‘shiladi va tanlangan kuni «Kun iqtibosi» bo‘lib hamma a‘zolarga va kanalga yuboriladi.
          </p>
          <Field label="Qaysi kuni" hint="Bo‘sh kunlardan birinchisi taklif qilingan">
            <Input type="date" value={day} onChange={(event) => setDay(event.target.value)} />
          </Field>
        </>
      ) : (
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-2">
            {preview ? (
              <img src={preview} alt="Kartochka" className="w-full rounded-lg shadow" />
            ) : (
              <div className="aspect-[4/5] w-full animate-pulse rounded-lg bg-app-surface" />
            )}
          </div>
          <div className="flex flex-col gap-3">
            <Field label="Dizayn">
              <div className="grid grid-cols-2 gap-1.5">
                {listing.styles.map((option) => (
                  <button
                    key={option.code}
                    type="button"
                    onClick={() => setStyle(option.code)}
                    className={`rounded-lg px-2 py-1.5 text-left text-sm ${style === option.code ? 'bg-app-button text-app-button-text' : 'bg-app-surface'}`}
                  >
                    {option.title}
                  </button>
                ))}
              </div>
            </Field>
            {sending && (
              <Field label="Rasm ostidagi matn" hint="Bo‘sh qoldirilsa — tayyor matn («Kitobxonlarimiz fikrlaridan…»)">
                <Textarea rows={3} maxLength={900} value={caption} onChange={(event) => setCaption(event.target.value)} />
              </Field>
            )}
            {action === 'channel' && (
              <Field label="Qachon" hint="Bo‘sh — hozir">
                <Input type="datetime-local" value={later} onChange={(event) => setLater(event.target.value)} />
              </Field>
            )}
            {action === 'members' && (
              <>
                <Field label="Fakultet">
                  <Select value={facultyId} onChange={(event) => setFacultyId(event.target.value)}>
                    <option value="">Hammasi</option>
                    {faculties.state.status === 'success' &&
                      faculties.state.data.map((faculty) => (
                        <option key={faculty.id} value={faculty.id}>
                          {faculty.name}
                        </option>
                      ))}
                  </Select>
                </Field>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Kurs">
                    <Input type="number" min={1} max={10} value={course} onChange={(event) => setCourse(event.target.value)} />
                  </Field>
                  <Field label="Guruh">
                    <Input value={group} maxLength={16} onChange={(event) => setGroup(event.target.value)} />
                  </Field>
                </div>
                <p className="text-sm text-app-hint">{count === null ? 'Hisoblanmoqda…' : `${count} nafar a'zoga boradi`}</p>
              </>
            )}
            {sending && !can('NOTIFICATION_SEND') && (
              <p className="text-sm text-app-danger">Buning uchun «A'zolarga xabar yuborish» huquqi ham kerak.</p>
            )}
            {action === 'card' && (
              <p className="text-sm text-app-hint">
                «📨 Menga yuborish» — kartochka bot chatingizga keladi: uni istalgan guruh, kanal yoki odamga uzatasiz (Forward).
              </p>
            )}
          </div>
        </div>
      )}
      <InlineError message={error} />
    </Modal>
  )
}

/** «💬 A'zolar fikrlari»: what members wrote — approve, feature, and use it anywhere. */
export function CommunityPage() {
  const { api } = useSession()
  const [tab, setTab] = useState<Status>('PENDING')
  const [kind, setKind] = useState('')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [dialog, setDialog] = useState<{ item: Item; action: Action } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const { state, reload } = useAsync(
    (signal) => {
      const params = new URLSearchParams({ status: tab })
      if (kind) params.set('kind', kind)
      if (query) params.set('q', query)
      return api<Listing>(`/api/v1/admin/community?${params.toString()}`, { signal })
    },
    [tab, kind, query],
  )

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(q.trim()), 350)
    return () => window.clearTimeout(timer)
  }, [q])

  async function moderate(item: Item, action: string) {
    setBusy(`${item.id}:${action}`)
    try {
      await api(`/api/v1/admin/community/${item.id}/moderate`, { method: 'POST', body: { action } })
      reload()
    } catch (err) {
      setNotice(err instanceof ApiError ? err.message : 'Bajarib bo‘lmadi')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="💬 A'zolar fikrlari"
        subtitle="A’zolar yuborgan iqtiboslar, fikrlar, kitob va tadbir taassurotlari, klub haqidagi e’tiroflar. Tasdiqlang — lentada chiqadi; «🙈 Yashirish» — hammaga ko‘rinmaydi. Xohlagan joyingizga uzating: kanal, a’zolar, kun iqtibosi yoki o‘zingizga (botda)."
      />
      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setTab(item.value)}
            className={`rounded-full px-3 py-1.5 text-sm ${tab === item.value ? 'bg-app-button text-app-button-text' : 'bg-app-surface'}`}
          >
            {item.label}
            {state.status === 'success' && <span className="ml-1 tabular-nums opacity-75">{state.data.counts[item.value]}</span>}
          </button>
        ))}
        <div className="ml-auto flex gap-2">
          <Select value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="">Barcha turlar</option>
            {state.status === 'success' &&
              state.data.kinds.map((option) => (
                <option key={option.code} value={option.code}>
                  {option.title}
                </option>
              ))}
          </Select>
          <Input placeholder="🔎 Matn yoki ism" value={q} onChange={(event) => setQ(event.target.value)} />
        </div>
      </div>
      {notice && (
        <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">{notice}</p>
      )}
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.items.length === 0 && (
        <Card className="p-8 text-center text-sm text-app-hint">Bu yerda hozircha hech narsa yo‘q.</Card>
      )}
      {state.status === 'success' && (
        <div className="grid gap-3 lg:grid-cols-2">
          {state.data.items.map((item) => (
            <Card key={item.id} className={`flex flex-col gap-2 p-4 ${item.featured ? 'ring-2 ring-amber-400/70' : ''}`}>
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <Badge>{item.kind_title}</Badge>
                {item.featured && <Badge tone="warning">⭐ Tanlangan</Badge>}
                {item.status === 'PENDING' && <Badge tone="info">⏳ Yangi</Badge>}
                {item.status === 'HIDDEN' && <Badge tone="danger">🙈 Yashirilgan</Badge>}
                <span className="ml-auto text-app-hint">❤️ {item.likes}</span>
              </div>
              <blockquote className="whitespace-pre-line text-[15px] italic leading-relaxed">{quoted(item.text)}</blockquote>
              {item.source && <p className="text-right text-sm text-app-hint">— {item.source}</p>}
              <p className="text-sm">
                <span className="font-medium">{item.member}</span>
                <span className="text-app-hint">
                  {item.member_details ? ` · ${item.member_details}` : ''} · {formatDateTime(item.created_at)}
                  {!item.show_name && ' · ismsiz ko‘rsatilsin'}
                </span>
              </p>
              {item.uses.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {item.uses.map((use, index) => (
                    <span key={index} title={`${use.by}, ${formatDateTime(use.at)}`}>
                      <Badge tone="success">{use.title}</Badge>
                    </span>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap gap-1.5 border-t border-app-border pt-2">
                {item.status !== 'APPROVED' && (
                  <Button loading={busy === `${item.id}:approve`} onClick={() => void moderate(item, 'approve')}>
                    ✅ Lentaga
                  </Button>
                )}
                <Button
                  variant="secondary"
                  loading={busy === `${item.id}:feature` || busy === `${item.id}:unfeature`}
                  onClick={() => void moderate(item, item.featured ? 'unfeature' : 'feature')}
                >
                  {item.featured ? '☆ Tanlangandan olish' : '⭐ Tanlash'}
                </Button>
                {item.status !== 'HIDDEN' && (
                  <Button variant="secondary" loading={busy === `${item.id}:hide`} onClick={() => void moderate(item, 'hide')}>
                    🙈 Yashirish
                  </Button>
                )}
                <Button variant="ghost" onClick={() => setDialog({ item, action: 'card' })}>
                  🖼 Kartochka
                </Button>
                <Button variant="ghost" onClick={() => setDialog({ item, action: 'channel' })}>
                  📣 Kanalga
                </Button>
                <Button variant="ghost" onClick={() => setDialog({ item, action: 'members' })}>
                  📢 A'zolarga
                </Button>
                <Button variant="ghost" onClick={() => setDialog({ item, action: 'quote' })}>
                  📜 Kun iqtibosi
                </Button>
                <Button variant="ghost" onClick={() => setDialog({ item, action: 'edit' })}>
                  ✏️
                </Button>
                <Button
                  variant="ghost"
                  onClick={() =>
                    void navigator.clipboard
                      ?.writeText(`«${item.text}»${item.source ? `\n— ${item.source}` : ''}\n\n✍️ ${item.author}`)
                      .then(() => setNotice('📋 Matn nusxalandi'))
                  }
                >
                  📋
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {dialog && state.status === 'success' && (
        <UseDialog
          item={dialog.item}
          action={dialog.action}
          listing={state.data}
          onClose={() => setDialog(null)}
          onDone={(message) => {
            setDialog(null)
            setNotice(message)
            reload()
          }}
        />
      )}
    </div>
  )
}
