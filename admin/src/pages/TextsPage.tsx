import { useMemo, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, InlineError, Input, Modal, PageHeader, Select, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import { formatDateTime } from '../utils/format'

interface TextItem {
  key: string
  kind: 'bot' | 'notify' | 'channel'
  group: string
  title: string
  default: string
  defaults: string[] | null
  builtin: string[]
  allowed: string[]
  variants: string[] | null
  rotate: boolean
  active: boolean | null
  hint: string | null
  updated_at: string | null
  updated_by: string | null
}

interface Listing {
  rotation: boolean
  items: TextItem[]
}

const KINDS: { value: string; label: string }[] = [
  { value: '', label: 'Hammasi' },
  { value: 'bot', label: '🤖 Bot xabarlari' },
  { value: 'notify', label: "🔔 A'zolarga bildirishnomalar" },
  { value: 'channel', label: '📣 Kanal postlari' },
]

/** Telegram shows <b>, <i> … — here a plain preview without the tags. */
function plain(text: string): string {
  return text.replace(/<[^>]+>/g, '')
}

function builtIn(item: TextItem): string[] {
  return item.defaults ?? [item.default, ...item.builtin]
}

function Editor({ item, onClose, onSaved }: { item: TextItem; onClose: () => void; onSaved: () => void }) {
  const { api } = useSession()
  const [variants, setVariants] = useState<string[]>(item.variants ?? builtIn(item))
  const [rotate, setRotate] = useState(item.rotate)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function run(action: string, work: () => Promise<unknown>, done?: string) {
    setBusy(action)
    setError(null)
    setNotice(null)
    try {
      await work()
      if (done) setNotice(done)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bajarib bo‘lmadi.')
    } finally {
      setBusy(null)
    }
  }

  const save = () =>
    run('save', async () => {
      await api(`/api/v1/admin/texts/${item.key}`, { method: 'PUT', body: { variants, rotate } })
      onSaved()
      onClose()
    })
  const reset = () =>
    run('reset', async () => {
      if (!window.confirm('Asl (dasturdagi) matnga qaytarilsinmi? Sizning variantlaringiz o‘chadi.')) return
      await api(`/api/v1/admin/texts/${item.key}`, { method: 'DELETE' })
      onSaved()
      onClose()
    })
  const preview = (text: string) =>
    run('preview', () => api(`/api/v1/admin/texts/${item.key}/preview`, { method: 'POST', body: { text } }), '📤 Botdagi chatingizga yuborildi — qanday ko‘rinishini tekshiring.')

  return (
    <Modal
      wide
      title={item.title}
      onClose={onClose}
      footer={
        <>
          {item.variants && (
            <Button variant="danger" loading={busy === 'reset'} onClick={() => void reset()}>
              ↩️ Asl holiga qaytarish
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>
            Bekor
          </Button>
          <Button loading={busy === 'save'} onClick={() => void save()}>
            💾 Saqlash
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-xs text-app-hint">
          <code>{item.key}</code> · {item.group}
        </p>
        {item.allowed.length > 0 ? (
          <div className="rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-200">
            Matnga avtomatik qo‘yiladigan qiymatlar (o‘zgartirmang, faqat joyini almashtirish mumkin):{' '}
            {item.allowed.map((name) => (
              <code key={name} className="mx-0.5 rounded bg-white/70 px-1 dark:bg-black/30">
                {`{${name}}`}
              </code>
            ))}
            {item.hint && <p className="mt-1 text-xs opacity-80">{item.hint}</p>}
          </div>
        ) : (
          <p className="text-sm text-app-hint">Bu xabarda avtomatik qiymat yo‘q — { } belgilarini ishlatmang.</p>
        )}
        <p className="text-sm text-app-hint">
          Formatlash: <code>&lt;b&gt;qalin&lt;/b&gt;</code>, <code>&lt;i&gt;qiya&lt;/i&gt;</code>, <code>&lt;u&gt;</code>,{' '}
          <code>&lt;code&gt;</code>, <code>&lt;a href="…"&gt;havola&lt;/a&gt;</code>. Har bir variant — xabarning boshqacha aytilishi;
          bot ularni navbatma-navbat yuboradi, bir xili ketma-ket takrorlanmaydi.
        </p>
        {variants.map((variant, index) => (
          <Card key={index} className="flex flex-col gap-2 p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{index + 1}-variant</span>
              <div className="flex gap-1">
                <Button variant="ghost" loading={busy === 'preview'} onClick={() => void preview(variant)}>
                  📤 Botda ko‘rish
                </Button>
                {variants.length > 1 && (
                  <Button variant="ghost" onClick={() => setVariants(variants.filter((_, i) => i !== index))}>
                    🗑
                  </Button>
                )}
              </div>
            </div>
            <Textarea
              rows={Math.min(10, Math.max(3, variant.split('\n').length + 1))}
              value={variant}
              maxLength={4000}
              onChange={(e) => setVariants(variants.map((v, i) => (i === index ? e.target.value : v)))}
            />
            <p className="text-right text-xs text-app-hint">{variant.length}/4000</p>
          </Card>
        ))}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button variant="secondary" disabled={variants.length >= 10} onClick={() => setVariants([...variants, variants[variants.length - 1] ?? ''])}>
            ➕ Yana variant
          </Button>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={rotate} onChange={(e) => setRotate(e.target.checked)} />
            Variantlarni navbatma-navbat yuborish (o‘chiq — doim 1-variant)
          </label>
        </div>
        <InlineError message={error} />
        {notice && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">{notice}</p>}
      </div>
    </Modal>
  )
}

/** «📝 Matnlar»: every word of the bot, the members' notifications and the channel posts — in the owner's hands. */
export function TextsPage() {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<Listing>('/api/v1/admin/texts', { signal }))
  const [kind, setKind] = useState('')
  const [group, setGroup] = useState('')
  const [query, setQuery] = useState('')
  const [onlyMine, setOnlyMine] = useState(false)
  const [editing, setEditing] = useState<TextItem | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const items = state.status === 'success' ? state.data.items : []
  const groups = useMemo(() => [...new Set(items.filter((item) => !kind || item.kind === kind).map((item) => item.group))], [items, kind])
  const shown = items.filter((item) => {
    if (kind && item.kind !== kind) return false
    if (group && item.group !== group) return false
    if (onlyMine && !item.variants) return false
    if (!query) return true
    const needle = query.toLowerCase()
    return [item.key, item.title, item.default, ...(item.variants ?? []), ...item.builtin].some((text) => text.toLowerCase().includes(needle))
  })
  const edited = items.filter((item) => item.variants).length

  async function toggle(item: TextItem) {
    await api(`/api/v1/admin/texts/${item.key}/active`, { method: 'PUT', body: { active: !item.active } })
    reload()
  }

  async function exportAll() {
    const data = await api<unknown>('/api/v1/admin/texts/export/all')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `kitobxon-matnlar-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  async function importFile(file: File) {
    try {
      const result = await api<{ imported: number }>('/api/v1/admin/texts/import/all', { method: 'POST', body: JSON.parse(await file.text()) })
      setMessage(`✅ ${result.imported} ta matn tiklandi.`)
      reload()
    } catch (err) {
      setMessage(err instanceof ApiError ? `⚠️ ${err.message}` : '⚠️ Faylni o‘qib bo‘lmadi.')
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="📝 Matnlar"
        subtitle="Bot yozadigan har bir xabar, a’zolarga boradigan bildirishnomalar va kanal postlari jumlalari. O‘zgartiring, bir nechta variant qo‘shing — bot ularni navbatma-navbat ishlatadi. Har bir o‘zgarish audit jurnaliga yoziladi va istalgan payt asliga qaytariladi."
        actions={
          <>
            <Button variant="secondary" onClick={() => void exportAll()}>
              ⬇️ Nusxa (fayl)
            </Button>
            <label className="inline-flex cursor-pointer items-center rounded-lg bg-app-surface px-3 py-2 text-sm font-medium">
              ⬆️ Fayldan tiklash
              <input type="file" accept="application/json" className="hidden" onChange={(e) => e.target.files?.[0] && void importFile(e.target.files[0])} />
            </label>
          </>
        }
      />
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <>
          <Card className="flex flex-wrap items-center gap-3 p-3 text-sm">
            <span>
              Jami <b>{items.length}</b> ta matn · siz o‘zgartirgan: <b>{edited}</b>
            </span>
            <span className="text-app-hint">
              Takrorlanmaslik (variantlar navbati): {state.data.rotation ? <Badge tone="success">yoqilgan</Badge> : <Badge>o‘chiq</Badge>} — Sozlamalar →
              «texts.rotate»
            </span>
          </Card>
          {message && <p className="rounded-lg bg-app-surface px-3 py-2 text-sm">{message}</p>}
          <div className="flex flex-wrap gap-2">
            <Select
              value={kind}
              onChange={(e) => {
                setKind(e.target.value)
                setGroup('')
              }}
            >
              {KINDS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <Select value={group} onChange={(e) => setGroup(e.target.value)}>
              <option value="">Barcha bo‘limlar</option>
              {groups.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
            <Input className="min-w-60 flex-1" placeholder="🔎 Matn bo‘yicha qidirish (masalan: davomat)" value={query} onChange={(e) => setQuery(e.target.value)} />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />
              Faqat o‘zgartirilganlar
            </label>
          </div>
          <div className="flex flex-col gap-2">
            {shown.length === 0 && <Card className="p-6 text-center text-sm text-app-hint">Hech narsa topilmadi.</Card>}
            {shown.slice(0, 200).map((item) => {
              const now = item.variants ?? builtIn(item)
              return (
                <Card key={item.key} className="flex flex-col gap-2 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{item.title}</p>
                      <p className="text-xs text-app-hint">
                        {item.group} · <code>{item.key}</code>
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                      {item.variants && <Badge tone="info">✏️ o‘zgartirilgan</Badge>}
                      {now.length > 1 && <Badge>{now.length} variant</Badge>}
                      {item.active === false && <Badge tone="danger">o‘chirilgan</Badge>}
                      {item.active !== null && (
                        <Button variant="ghost" onClick={() => void toggle(item)}>
                          {item.active ? '🔕 O‘chirish' : '🔔 Yoqish'}
                        </Button>
                      )}
                      <Button variant="secondary" onClick={() => setEditing(item)}>
                        ✏️ Tahrirlash
                      </Button>
                    </div>
                  </div>
                  <p className="line-clamp-3 whitespace-pre-line rounded-lg bg-app-surface px-3 py-2 text-sm">{plain(now[0])}</p>
                  {item.updated_at && (
                    <p className="text-xs text-app-hint">
                      O‘zgartirdi: {item.updated_by ?? '—'}, {formatDateTime(item.updated_at)}
                    </p>
                  )}
                </Card>
              )
            })}
            {shown.length > 200 && <p className="text-center text-sm text-app-hint">Yana {shown.length - 200} ta — qidiruv bilan toraytiring.</p>}
          </div>
        </>
      )}
      {editing && <Editor item={editing} onClose={() => setEditing(null)} onSaved={reload} />}
    </div>
  )
}
