import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminTest, AdminTestDetail, Book, Page, TestState } from '../types/api'
import { formatDateTime, fromLocalInput } from '../utils/format'
import { navigate } from '../utils/router'

const STATE: Record<TestState, { label: string; tone: 'success' | 'info' | 'neutral' | 'warning' }> = {
  DRAFT: { label: 'Qoralama', tone: 'warning' },
  UPCOMING: { label: 'Kutilmoqda', tone: 'info' },
  OPEN: { label: 'Ochiq', tone: 'success' },
  CLOSED: { label: 'Yopilgan', tone: 'neutral' },
}

export function TestStateBadge({ state }: { state: TestState }) {
  return <Badge tone={STATE[state].tone}>{STATE[state].label}</Badge>
}

function NewTestModal({ onClose }: { onClose: () => void }) {
  const { api } = useSession()
  const books = useAsync((signal) => api<Page<Book>>('/api/v1/admin/books?limit=200', { signal }))
  const [form, setForm] = useState({ title: '', book_id: '', starts_at: '', ends_at: '', duration_minutes: '15' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [field]: e.target.value })

  async function create() {
    setBusy(true)
    setError(null)
    try {
      const test = await api<AdminTestDetail>('/api/v1/admin/tests', {
        method: 'POST',
        body: {
          title: form.title.trim(),
          book_id: form.book_id || null,
          starts_at: fromLocalInput(form.starts_at),
          ends_at: fromLocalInput(form.ends_at),
          duration_minutes: Number(form.duration_minutes),
        },
      })
      navigate(`/tests/${test.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
      setBusy(false)
    }
  }

  return (
    <Modal
      title="Yangi test"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button
            loading={busy}
            disabled={form.title.trim().length < 2 || !form.starts_at || !form.ends_at || !form.duration_minutes}
            onClick={() => void create()}
          >
            Yaratish va savollarga o'tish
          </Button>
        </>
      }
    >
      <Field label="Test nomi *">
        <Input value={form.title} onChange={set('title')} maxLength={255} placeholder="«O'tkan kunlar» — 1-test" />
      </Field>
      <Field label="Kitob" hint="Testdan o'tgan a'zoning kitobni o'qigani tasdiqlanadi">
        <Select value={form.book_id} onChange={set('book_id')}>
          <option value="">— Tanlanmagan —</option>
          {books.state.status === 'success' &&
            books.state.data.items.map((book) => (
              <option key={book.id} value={book.id}>
                {book.title}
              </option>
            ))}
        </Select>
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Ochiladi * (Toshkent vaqti)">
          <Input type="datetime-local" value={form.starts_at} onChange={set('starts_at')} />
        </Field>
        <Field label="Yopiladi *">
          <Input type="datetime-local" value={form.ends_at} onChange={set('ends_at')} />
        </Field>
      </div>
      <Field label="Yechish uchun vaqt (daqiqa) *" hint="Har bir a'zo boshlagan paytdan hisoblanadi">
        <Input type="number" min={1} max={600} value={form.duration_minutes} onChange={set('duration_minutes')} />
      </Field>
      <InlineError message={error} />
    </Modal>
  )
}

export function TestsPage() {
  const { api, can } = useSession()
  const [creating, setCreating] = useState(false)
  const { state, reload } = useAsync((signal) => api<Page<AdminTest>>('/api/v1/admin/tests?limit=200', { signal }))

  return (
    <>
      <PageHeader
        title="Testlar"
        subtitle="Test qoralama holatida tayyorlanadi, «E'lon qilish»dan so'ng a'zolar Mini App'da ko'radi. Ballni faqat server hisoblaydi."
        actions={can('TEST_CREATE') && <Button onClick={() => setCreating(true)}>+ Yangi test</Button>}
      />
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={['Test', 'Vaqti', 'Holat', 'Savollar', 'Qatnashchilar', '']}>
            {state.data.items.length === 0 && <EmptyRow colSpan={6} text="Testlar hali yaratilmagan" />}
            {state.data.items.map((test) => (
              <tr key={test.id}>
                <td className="px-4 py-2.5">
                  <p className="font-medium">{test.title}</p>
                  <p className="text-xs text-app-hint">
                    {test.book_title ? `📚 ${test.book_title} · ` : ''}⏱ {test.duration_minutes} daq · 🏆 {test.max_score} ball
                  </p>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-xs">
                  {formatDateTime(test.starts_at)}
                  <br />
                  {formatDateTime(test.ends_at)}
                </td>
                <td className="px-4 py-2.5">
                  <TestStateBadge state={test.state} />
                </td>
                <td className="px-4 py-2.5 tabular-nums">
                  {test.questions_per_attempt && test.questions_per_attempt < test.question_count
                    ? `${test.questions_per_attempt} / ${test.question_count}`
                    : test.question_count}
                </td>
                <td className="px-4 py-2.5 tabular-nums">{test.participant_count}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  <Button variant="ghost" onClick={() => navigate(`/tests/${test.id}/results`)}>
                    Natijalar
                  </Button>
                  <Button variant="ghost" onClick={() => navigate(`/tests/${test.id}`)}>
                    {can('TEST_EDIT') ? 'Tahrirlash' : "Ko'rish"}
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {creating && <NewTestModal onClose={() => setCreating(false)} />}
    </>
  )
}
