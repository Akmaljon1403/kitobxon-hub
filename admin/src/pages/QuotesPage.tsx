import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Pagination, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Book, Page, Quote, QuoteStatus } from '../types/api'
import { QUOTE_STATUS_LABELS, formatDate } from '../utils/format'

const LIMIT = 50

export function QuotesPage() {
  const { api, can } = useSession()
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<Quote | null>(null)
  const { state, reload } = useAsync(
    (signal) => api<Page<Quote>>(`/api/v1/admin/quotes?limit=${LIMIT}&offset=${offset}`, { signal }),
    [offset],
  )

  async function remove(quote: Quote) {
    if (!window.confirm("Iqtibosni o'chirasizmi?")) return
    try {
      await api(`/api/v1/admin/quotes/${quote.id}`, { method: 'DELETE' })
      reload()
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : "O'chirib bo'lmadi.")
    }
  }

  return (
    <>
      <PageHeader
        title="Iqtiboslar"
        subtitle="Iqtiboslar a'zolarning «💬 A'zolar fikrlari»dagi o'z iqtiboslaridan keladi — admin iqtibos o'ylab topmaydi. Bu yerda ularni «Kun iqtibosi» qilib rejalashtirasiz: «Rejalashtirilgan» iqtibos belgilangan kuni yuboriladi."
      />
      <details className="rounded-xl border border-app-border bg-app-bg p-3 text-sm">
        <summary className="cursor-pointer font-medium">ℹ️ Holatlar nimani bildiradi?</summary>
        <ul className="mt-2 flex flex-col gap-1 text-app-hint">
          <li>
            <b className="text-app-text">Qoralama</b> — saqlangan, lekin hech kimga yuborilmaydi. Tahrir qilib turish uchun.
          </li>
          <li>
            <b className="text-app-text">Rejalashtirilgan</b> — sana belgilangan: o'sha kuni Sozlamalardagi vaqtda (odatda 09:00) «💬 Kun
            iqtibosi» bo'lib a'zolarga va kanalga chiqadi. Sana qo'yilmasa, yuborilmaydi.
          </li>
          <li>
            <b className="text-app-text">Yuborilgan</b> — allaqachon yuborilgan; kitob sahifasida ko'rinishda qoladi.
          </li>
          <li>
            <b className="text-app-text">Arxiv</b> — yashirilgan: yuborilmaydi va ilovada ko'rinmaydi, lekin o'chirilmagan.
          </li>
        </ul>
      </details>
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <>
            <Table head={['Iqtibos', 'Kitob', 'Sana', 'Holat', '']}>
              {state.data.items.length === 0 && (
                <EmptyRow colSpan={5} text="Hali iqtibos yo'q — a'zolar «A'zolar fikrlari»da iqtibos ulashsa, shu yerda ko'rinadi" />
              )}
              {state.data.items.map((quote) => (
                <tr key={quote.id}>
                  <td className="max-w-md px-4 py-2.5">
                    <p className="line-clamp-2">«{quote.text}»</p>
                    <p className="text-xs text-app-hint">
                      {quote.author ?? ''} {quote.source ? `· ${quote.source}` : ''}
                    </p>
                  </td>
                  <td className="px-4 py-2.5">{quote.book_title ?? '—'}</td>
                  <td className="whitespace-nowrap px-4 py-2.5">{formatDate(quote.scheduled_date)}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={quote.status === 'SCHEDULED' ? 'info' : quote.status === 'SENT' ? 'success' : 'neutral'}>
                      {QUOTE_STATUS_LABELS[quote.status]}
                    </Badge>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-right">
                    {can('BOOK_EDIT') && (
                      <Button variant="ghost" onClick={() => setEditing(quote)}>
                        Tahrirlash
                      </Button>
                    )}
                    {can('BOOK_DELETE') && (
                      <Button variant="ghost" className="text-app-danger" onClick={() => void remove(quote)}>
                        O'chirish
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
            <Pagination total={state.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
      {editing && (
        <QuoteModal
          quote={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
    </>
  )
}

function QuoteModal({ quote, onClose, onSaved }: { quote: Quote; onClose: () => void; onSaved: () => void }) {
  const { api } = useSession()
  const books = useAsync((signal) => api<Page<Book>>('/api/v1/admin/books?limit=200', { signal }))
  const [form, setForm] = useState({
    book_id: quote.book_id ?? '',
    text: quote.text ?? '',
    author: quote.author ?? '',
    source: quote.source ?? '',
    scheduled_date: quote.scheduled_date ?? '',
    status: quote.status as QuoteStatus,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api(`/api/v1/admin/quotes/${quote.id}`, {
        method: 'PATCH',
        body: {
          book_id: form.book_id || null,
          text: form.text.trim(),
          author: form.author.trim() || null,
          source: form.source.trim() || null,
          scheduled_date: form.scheduled_date || null,
          status: form.status,
        },
      })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title="Iqtibosni tahrirlash"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button onClick={save} loading={busy} disabled={form.text.trim().length < 3}>
            Saqlash
          </Button>
        </>
      }
    >
      <Field label="Iqtibos matni *">
        <Textarea value={form.text} maxLength={2000} onChange={(e) => setForm({ ...form, text: e.target.value })} />
      </Field>
      <Field label="Kitob">
        <Select value={form.book_id} onChange={(e) => setForm({ ...form, book_id: e.target.value })}>
          <option value="">— Kitobga bog'lanmagan —</option>
          {books.state.status === 'success' &&
            books.state.data.items.map((book) => (
              <option key={book.id} value={book.id}>
                {book.title} — {book.author}
              </option>
            ))}
        </Select>
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Muallif">
          <Input value={form.author} maxLength={255} onChange={(e) => setForm({ ...form, author: e.target.value })} />
        </Field>
        <Field label="Manba / bet" hint="Masalan: 45-bet">
          <Input value={form.source} maxLength={255} onChange={(e) => setForm({ ...form, source: e.target.value })} />
        </Field>
        <Field label="Yuboriladigan sana">
          <Input type="date" value={form.scheduled_date} onChange={(e) => setForm({ ...form, scheduled_date: e.target.value })} />
        </Field>
        <Field label="Holat">
          <Select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as QuoteStatus })}>
            {Object.entries(QUOTE_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <InlineError message={error} />
    </Modal>
  )
}
