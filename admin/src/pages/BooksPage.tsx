import { useRef, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { API_BASE, ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Book, BookStatus, BookSuggestion, Page, Reader } from '../types/api'
import { BOOK_STATUS_LABELS, formatDate } from '../utils/format'

const STATUS_TONE: Record<BookStatus, 'success' | 'info' | 'neutral' | 'warning' | 'danger'> = {
  SUGGESTED: 'info',
  ACTIVE: 'success',
  DRAFT: 'warning',
  COMPLETED: 'info',
  ARCHIVED: 'neutral',
  REJECTED: 'danger',
}

type BookForm = {
  title: string
  author: string
  description: string
  cover_url: string
  source_url: string
  pages: string
  status: BookStatus
}

const EMPTY: BookForm = {
  title: '',
  author: '',
  description: '',
  cover_url: '',
  source_url: '',
  pages: '',
  status: 'DRAFT',
}

function toForm(book: Book): BookForm {
  return {
    title: book.title,
    author: book.author,
    description: book.description ?? '',
    cover_url: book.cover_url ?? '',
    source_url: book.source_url ?? '',
    pages: book.pages ? String(book.pages) : '',
    status: book.status,
  }
}

function toPayload(form: BookForm) {
  return {
    title: form.title.trim(),
    author: form.author.trim(),
    description: form.description.trim() || null,
    cover_url: form.cover_url.trim() || null,
    source_url: form.source_url.trim() || null,
    pages: form.pages ? Number(form.pages) : null,
    status: form.status,
  }
}

export function BooksPage() {
  const { api, can } = useSession()
  const [status, setStatus] = useState('')
  const [editing, setEditing] = useState<Book | 'new' | null>(null)
  const [readersOf, setReadersOf] = useState<Book | null>(null)
  const { state, reload } = useAsync(
    (signal) => api<Page<Book>>(`/api/v1/admin/books?limit=200${status ? `&status=${status}` : ''}`, { signal }),
    [status],
  )

  async function remove(book: Book) {
    if (!window.confirm(`«${book.title}» kitobini o'chirasizmi? A'zolar uni boshqa ko'rmaydi.`)) return
    try {
      await api(`/api/v1/admin/books/${book.id}`, { method: 'DELETE' })
      reload()
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : "O'chirib bo'lmadi.")
    }
  }

  return (
    <>
      <PageHeader
        title="Kitoblar"
        subtitle="Qoralama kitoblarni a'zolar ko'rmaydi. «Faol» holatiga o'tkazilganda Mini App'da paydo bo'ladi."
        actions={can('BOOK_CREATE') && <Button onClick={() => setEditing('new')}>+ Yangi kitob</Button>}
      />
      {can('BOOK_EDIT') && <BookSuggestions onChanged={reload} />}
      <Card>
        <div className="border-b border-app-border p-4">
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-xs" aria-label="Holat">
            <option value="">Barcha holatlar</option>
            {Object.entries(BOOK_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={['Kitob', 'Holat', "O'quvchilar", '']}>
            {state.data.items.length === 0 && <EmptyRow colSpan={4} text="Kitoblar hali qo'shilmagan" />}
            {state.data.items.map((book) => (
              <tr key={book.id}>
                <td className="px-4 py-2.5">
                  <p className="font-medium">{book.title}</p>
                  <p className="text-xs text-app-hint">{book.author}</p>
                </td>
                <td className="px-4 py-2.5">
                  <Badge tone={STATUS_TONE[book.status]}>{BOOK_STATUS_LABELS[book.status]}</Badge>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 tabular-nums">
                  {book.readers_count} / ✓ {book.completed_count}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  <Button variant="ghost" onClick={() => setReadersOf(book)}>
                    O'quvchilar
                  </Button>
                  {can('BOOK_EDIT') && (
                    <Button variant="ghost" onClick={() => setEditing(book)}>
                      Tahrirlash
                    </Button>
                  )}
                  {can('BOOK_DELETE') && (
                    <Button variant="ghost" className="text-app-danger" onClick={() => void remove(book)}>
                      O'chirish
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {editing && (
        <BookFormModal
          book={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
      {readersOf && <ReadersModal book={readersOf} onClose={() => setReadersOf(null)} onChanged={reload} />}
    </>
  )
}

/** Members' book suggestions awaiting review; the admin publishes or rejects each one. */
function BookSuggestions({ onChanged }: { onChanged: () => void }) {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<BookSuggestion[]>('/api/v1/admin/book-suggestions', { signal }))
  const [busyId, setBusyId] = useState<string | null>(null)

  async function act(suggestion: BookSuggestion, action: 'publish' | 'reject') {
    let body: Record<string, unknown> | undefined
    if (action === 'reject') {
      const reason = window.prompt(`«${suggestion.title}» taklifini rad etasizmi?\n\nSabab (ixtiyoriy, a'zoga ko'rinadi):`)
      if (reason === null) return
      body = { reason: reason.trim() || null }
    }
    setBusyId(suggestion.id)
    try {
      await api(`/api/v1/admin/books/${suggestion.id}/${action}`, { method: 'POST', body })
      reload()
      onChanged()
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusyId(null)
    }
  }

  if (state.status !== 'success' || state.data.length === 0) return null
  return (
    <Card className="mb-4">
      <div className="flex items-center gap-2 border-b border-app-border px-4 py-3">
        <h2 className="font-semibold">📥 A'zolar takliflari</h2>
        <Badge tone="info">{state.data.length}</Badge>
        <span className="text-xs text-app-hint">A'zolar klub kutubxonasiga taklif qilgan kitoblar</span>
      </div>
      <Table head={['Kitob', 'Kim taklif qildi', '']}>
        {state.data.map((s) => (
          <tr key={s.id}>
            <td className="px-4 py-2.5">
              <p className="font-medium">{s.title}</p>
              <p className="text-xs text-app-hint">
                {s.author}
                {s.pages ? ` · ${s.pages} bet` : ''}
                {s.source_url ? (
                  <>
                    {' · '}
                    <a href={s.source_url} target="_blank" rel="noreferrer" className="text-app-link hover:underline">
                      havola
                    </a>
                  </>
                ) : (
                  ''
                )}
              </p>
              {s.description && <p className="mt-1 max-w-prose text-xs text-app-hint">{s.description}</p>}
            </td>
            <td className="px-4 py-2.5">
              {s.suggested_by}
              <p className="text-xs text-app-hint">
                {s.faculty_name ?? ''} {s.course ? `· ${s.course}-kurs` : ''} {s.group_name ?? ''} · {formatDate(s.created_at)}
              </p>
            </td>
            <td className="whitespace-nowrap px-4 py-2.5 text-right">
              <Button loading={busyId === s.id} onClick={() => void act(s, 'publish')}>
                ✅ E'lon qilish
              </Button>
              <Button variant="ghost" className="text-app-danger" disabled={busyId === s.id} onClick={() => void act(s, 'reject')}>
                Rad etish
              </Button>
            </td>
          </tr>
        ))}
      </Table>
    </Card>
  )
}

/** The book's own cover picture: shown to members and in the channel posts of the book and its events. */
function CoverUpload({ book }: { book: Book }) {
  const { api } = useSession()
  const [image, setImage] = useState<string | null>(book.cover_image ?? null)
  const [uploaded, setUploaded] = useState(Boolean(book.cover_uploaded))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)

  async function send(file: File | null) {
    setBusy(true)
    setError(null)
    try {
      let next: Book
      if (file) {
        const form = new FormData()
        form.append('file', file)
        next = await api<Book>(`/api/v1/admin/books/${book.id}/cover`, { method: 'PUT', body: form })
      } else {
        next = await api<Book>(`/api/v1/admin/books/${book.id}/cover`, { method: 'DELETE' })
      }
      setImage(next.cover_image ?? null)
      setUploaded(Boolean(next.cover_uploaded))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Rasmni yuklab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  const src = image ? (image.startsWith('/') ? `${API_BASE}${image}` : image) : null
  return (
    <div className="flex items-start gap-3 rounded-lg border border-app-border p-3 sm:col-span-2">
      {src ? <img src={src} alt="Muqova" className="h-28 w-20 rounded object-cover" /> : <div className="h-28 w-20 rounded bg-app-surface" />}
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium">📕 Muqova rasmi</p>
        <p className="text-xs text-app-hint">A'zolar ilovada ko'radi; kitob va shu kitob bo'yicha tadbir posti kanalga muqova bilan chiqadi.</p>
        <input ref={input} type="file" accept="image/*" className="hidden" onChange={(e) => void send(e.target.files?.[0] ?? null)} />
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" loading={busy} onClick={() => input.current?.click()}>
            🖼 {uploaded ? 'Boshqa rasm' : 'Rasm yuklash'}
          </Button>
          {uploaded && (
            <Button variant="ghost" className="text-app-danger" disabled={busy} onClick={() => void send(null)}>
              Olib tashlash
            </Button>
          )}
        </div>
        <InlineError message={error} />
      </div>
    </div>
  )
}

function BookFormModal({ book, onClose, onSaved }: { book: Book | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useSession()
  const [form, setForm] = useState<BookForm>(book ? toForm(book) : EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (field: keyof BookForm) => (event: { target: { value: string } }) =>
    setForm({ ...form, [field]: event.target.value })

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api(book ? `/api/v1/admin/books/${book.id}` : '/api/v1/admin/books', {
        method: book ? 'PATCH' : 'POST',
        body: toPayload(form),
      })
      onSaved()
    } catch (err) {
      const details = err instanceof ApiError && err.code === 'VALIDATION_ERROR' ? " Havolalar https:// bilan boshlanishi kerak." : ''
      setError(err instanceof ApiError ? err.message + details : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={book ? 'Kitobni tahrirlash' : 'Yangi kitob'}
      onClose={onClose}
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button onClick={save} loading={busy} disabled={!form.title.trim() || !form.author.trim()}>
            Saqlash
          </Button>
        </>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Kitob nomi *">
          <Input value={form.title} onChange={set('title')} maxLength={255} />
        </Field>
        <Field label="Muallif *">
          <Input value={form.author} onChange={set('author')} maxLength={255} />
        </Field>
        {book ? (
          <CoverUpload book={book} />
        ) : (
          <p className="text-xs text-app-hint sm:col-span-2">📕 Muqova rasmini kitob saqlangandan keyin yuklaysiz.</p>
        )}
        <Field label="Yoki muqova havolasi" hint="Rasm yuklanmagan bo'lsa ishlatiladi: https://.../muqova.jpg">
          <Input value={form.cover_url} onChange={set('cover_url')} placeholder="https://" />
        </Field>
        <Field label="Kitob havolasi" hint="A'zolar kitobni shu havola orqali ochadi">
          <Input value={form.source_url} onChange={set('source_url')} placeholder="https://" />
        </Field>
        <Field label="Betlar soni">
          <Input type="number" min={1} value={form.pages} onChange={set('pages')} />
        </Field>
        <Field label="Holat">
          <Select value={form.status} onChange={set('status')}>
            {Object.entries(BOOK_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Tavsif">
        <Textarea value={form.description} onChange={set('description')} maxLength={5000} />
      </Field>
      <InlineError message={error} />
    </Modal>
  )
}

function ReadersModal({ book, onClose, onChanged }: { book: Book; onClose: () => void; onChanged: () => void }) {
  const { api, can } = useSession()
  const { state, reload } = useAsync((signal) => api<Reader[]>(`/api/v1/admin/books/${book.id}/readers`, { signal }), [book.id])
  const [busyId, setBusyId] = useState<string | null>(null)

  async function verify(reader: Reader) {
    setBusyId(reader.user_id)
    try {
      await api(`/api/v1/admin/books/${book.id}/readers/${reader.user_id}/verify`, { method: 'POST' })
      reload()
      onChanged()
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Modal title={`«${book.title}» — o'quvchilar`} onClose={onClose} wide>
      <p className="text-sm text-app-hint">
        «Tasdiqlash» — a'zo kitobni o'qiganini tasdiqlaydi va kitob uchun ballni (bir marta) beradi.
      </p>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <Table head={["A'zo", 'Guruh', 'Holat', '']}>
          {state.data.length === 0 && <EmptyRow colSpan={4} text="Hali hech kim o'qishni boshlamagan" />}
          {state.data.map((reader) => (
            <tr key={reader.user_id}>
              <td className="px-4 py-2.5">
                {reader.last_name} {reader.first_name}
                <p className="text-xs text-app-hint">{reader.faculty_name ?? ''}</p>
              </td>
              <td className="whitespace-nowrap px-4 py-2.5">
                {reader.course ? `${reader.course}-kurs` : ''} {reader.group_name ?? ''}
              </td>
              <td className="px-4 py-2.5">
                {reader.verified_at ? (
                  <Badge tone="success">✅ Tasdiqlangan</Badge>
                ) : reader.status === 'COMPLETED' ? (
                  <Badge tone="info">Tugatdim deb belgiladi · {formatDate(reader.completed_at)}</Badge>
                ) : (
                  <Badge>O'qimoqda</Badge>
                )}
              </td>
              <td className="px-4 py-2.5 text-right">
                {!reader.verified_at && can('BOOK_EDIT') && (
                  <Button variant="secondary" loading={busyId === reader.user_id} onClick={() => void verify(reader)}>
                    Tasdiqlash
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </Modal>
  )
}
