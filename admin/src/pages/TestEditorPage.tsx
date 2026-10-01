import { useEffect, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, Field, InlineError, Input, PageHeader, Select, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminQuestion, AdminTestDetail, Book, Page, QuestionType } from '../types/api'
import { formatDateTime, fromLocalInput, toLocalInput } from '../utils/format'
import { navigate } from '../utils/router'
import { TestStateBadge } from './TestsPage'

function blankQuestion(): AdminQuestion {
  return {
    type: 'SINGLE_CHOICE',
    text: '',
    points: 1,
    explanation: null,
    options: [
      { text: '', is_correct: true },
      { text: '', is_correct: false },
      { text: '', is_correct: false },
    ],
  }
}

/** Mirrors the server rules so the admin sees problems before saving. */
function problemsOf(question: AdminQuestion): string[] {
  const problems: string[] = []
  const correct = question.options.filter((o) => o.is_correct).length
  if (!question.text.trim()) problems.push('savol matni yozilmagan')
  if (question.options.length < 2) problems.push('kamida 2 ta variant kerak')
  if (question.options.some((o) => !o.text.trim())) problems.push("bo'sh variant bor")
  const texts = question.options.map((o) => o.text.trim().toLowerCase())
  if (new Set(texts).size !== texts.length) problems.push('variantlar takrorlangan')
  if (question.type === 'SINGLE_CHOICE' && correct !== 1) problems.push("bitta to'g'ri javob belgilang")
  if (question.type === 'MULTIPLE_CHOICE' && correct < 1) problems.push("kamida bitta to'g'ri javob belgilang")
  return problems
}

function SettingsForm({ test, readOnlyScores, onSaved }: { test: AdminTestDetail; readOnlyScores: boolean; onSaved: () => void }) {
  const { api, can } = useSession()
  const books = useAsync((signal) => api<Page<Book>>('/api/v1/admin/books?limit=200', { signal }))
  const initial = {
    title: test.title,
    description: test.description ?? '',
    book_id: test.book_id ?? '',
    starts_at: toLocalInput(test.starts_at),
    ends_at: toLocalInput(test.ends_at),
    duration_minutes: String(test.duration_minutes),
    max_score: String(test.max_score),
    passing_score: String(test.passing_score),
    attempts_allowed: String(test.attempts_allowed),
    shuffle_questions: test.shuffle_questions,
    shuffle_options: test.shuffle_options,
  }
  const [form, setForm] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const editable = can('TEST_EDIT')
  const set = (field: keyof typeof form) => (e: { target: { value: string } }) => {
    setSaved(false)
    setForm({ ...form, [field]: e.target.value })
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api(`/api/v1/admin/tests/${test.id}`, {
        method: 'PATCH',
        body: {
          title: form.title.trim(),
          description: form.description.trim() || null,
          book_id: form.book_id || null,
          starts_at: fromLocalInput(form.starts_at),
          ends_at: fromLocalInput(form.ends_at),
          duration_minutes: Number(form.duration_minutes),
          max_score: Number(form.max_score),
          passing_score: Number(form.passing_score),
          attempts_allowed: Number(form.attempts_allowed),
          shuffle_questions: form.shuffle_questions,
          shuffle_options: form.shuffle_options,
        },
      })
      setSaved(true)
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <h2 className="font-semibold">Sozlamalar</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Test nomi *">
          <Input value={form.title} onChange={set('title')} disabled={!editable} maxLength={255} />
        </Field>
        <Field label="Kitob">
          <Select value={form.book_id} onChange={set('book_id')} disabled={!editable}>
            <option value="">— Tanlanmagan —</option>
            {books.state.status === 'success' &&
              books.state.data.items.map((book) => (
                <option key={book.id} value={book.id}>
                  {book.title}
                </option>
              ))}
          </Select>
        </Field>
        <Field label="Ochiladi (Toshkent vaqti)">
          <Input type="datetime-local" value={form.starts_at} onChange={set('starts_at')} disabled={!editable} />
        </Field>
        <Field label="Yopiladi" hint="Yopilgach to'g'ri javoblar ochiladi va o'rinlar uchun bonus beriladi">
          <Input type="datetime-local" value={form.ends_at} onChange={set('ends_at')} disabled={!editable} />
        </Field>
        <Field label="Yechish vaqti (daqiqa)">
          <Input type="number" min={1} max={600} value={form.duration_minutes} onChange={set('duration_minutes')} disabled={!editable} />
        </Field>
        <Field label="Urinishlar soni" hint="Bir nechta bo'lsa, eng yaxshi natija hisoblanadi">
          <Input type="number" min={1} max={10} value={form.attempts_allowed} onChange={set('attempts_allowed')} disabled={!editable} />
        </Field>
        <Field label="Maksimal ball" hint={readOnlyScores ? 'Test boshlangan — o\'zgartirib bo\'lmaydi' : 'Reytingga qo\'shiladigan eng yuqori ball'}>
          <Input type="number" min={1} max={1000} value={form.max_score} onChange={set('max_score')} disabled={!editable || readOnlyScores} />
        </Field>
        <Field label="O'tish bali" hint="Bundan kam natija ball bermaydi (0 — chegarasiz)">
          <Input type="number" min={0} max={1000} value={form.passing_score} onChange={set('passing_score')} disabled={!editable || readOnlyScores} />
        </Field>
      </div>
      <Field label="Tavsif">
        <Textarea value={form.description} onChange={set('description')} maxLength={5000} disabled={!editable} />
      </Field>
      <div className="flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.shuffle_questions}
            disabled={!editable}
            onChange={(e) => setForm({ ...form, shuffle_questions: e.target.checked })}
          />
          Savollar tartibini aralashtirish
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.shuffle_options}
            disabled={!editable}
            onChange={(e) => setForm({ ...form, shuffle_options: e.target.checked })}
          />
          Javob variantlarini aralashtirish
        </label>
      </div>
      <InlineError message={error} />
      {editable && (
        <div className="flex items-center justify-end gap-3">
          {saved && <span className="text-sm text-emerald-600">✓ Saqlandi</span>}
          <Button loading={busy} onClick={() => void save()}>
            Sozlamalarni saqlash
          </Button>
        </div>
      )}
    </Card>
  )
}

function QuestionEditor({
  index,
  question,
  total,
  readOnly,
  onChange,
  onMove,
  onRemove,
}: {
  index: number
  question: AdminQuestion
  total: number
  readOnly: boolean
  onChange: (question: AdminQuestion) => void
  onMove: (delta: number) => void
  onRemove: () => void
}) {
  const problems = problemsOf(question)
  const setOption = (optionIndex: number, patch: Partial<AdminQuestion['options'][number]>) => {
    let options = question.options.map((o, i) => (i === optionIndex ? { ...o, ...patch } : o))
    if (patch.is_correct && question.type === 'SINGLE_CHOICE') {
      options = options.map((o, i) => ({ ...o, is_correct: i === optionIndex }))
    }
    onChange({ ...question, options })
  }
  const setType = (type: QuestionType) => {
    let options = question.options
    if (type === 'SINGLE_CHOICE' && options.filter((o) => o.is_correct).length !== 1) {
      const first = Math.max(0, options.findIndex((o) => o.is_correct))
      options = options.map((o, i) => ({ ...o, is_correct: i === first }))
    }
    onChange({ ...question, type, options })
  }

  return (
    <Card className={`flex flex-col gap-3 p-4 ${problems.length && !readOnly ? 'border-amber-400' : ''}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">{index + 1}-savol</h3>
        {!readOnly && (
          <div className="flex gap-1">
            <Button variant="ghost" disabled={index === 0} onClick={() => onMove(-1)} aria-label="Yuqoriga">
              ↑
            </Button>
            <Button variant="ghost" disabled={index === total - 1} onClick={() => onMove(1)} aria-label="Pastga">
              ↓
            </Button>
            <Button variant="ghost" className="text-app-danger" onClick={onRemove}>
              O'chirish
            </Button>
          </div>
        )}
      </div>
      <Textarea
        value={question.text}
        onChange={(e) => onChange({ ...question, text: e.target.value })}
        placeholder="Savol matni"
        aria-label={`${index + 1}-savol matni`}
        maxLength={2000}
        disabled={readOnly}
      />
      <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
        <Field label="Turi">
          <Select value={question.type} onChange={(e) => setType(e.target.value as QuestionType)} disabled={readOnly}>
            <option value="SINGLE_CHOICE">Bitta to'g'ri javob</option>
            <option value="MULTIPLE_CHOICE">Bir nechta to'g'ri javob (hammasi to'g'ri bo'lsa ball)</option>
          </Select>
        </Field>
        <Field label="Ball">
          <Input
            type="number"
            min={1}
            max={100}
            value={question.points}
            onChange={(e) => onChange({ ...question, points: Number(e.target.value) || 1 })}
            disabled={readOnly}
          />
        </Field>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm text-app-hint">Variantlar — to'g'risini belgilang</legend>
        {question.options.map((option, optionIndex) => (
          <div key={optionIndex} className="flex items-center gap-2">
            <input
              type={question.type === 'SINGLE_CHOICE' ? 'radio' : 'checkbox'}
              name={`q${index}-correct`}
              checked={option.is_correct}
              onChange={(e) => setOption(optionIndex, { is_correct: e.target.checked })}
              aria-label={`${String.fromCharCode(65 + optionIndex)} variant to'g'ri`}
              disabled={readOnly}
              className="size-4"
            />
            <Input
              value={option.text}
              onChange={(e) => setOption(optionIndex, { text: e.target.value })}
              placeholder={`${String.fromCharCode(65 + optionIndex)} variant`}
              maxLength={500}
              disabled={readOnly}
            />
            {!readOnly && question.options.length > 2 && (
              <Button
                variant="ghost"
                aria-label="Variantni o'chirish"
                onClick={() => onChange({ ...question, options: question.options.filter((_, i) => i !== optionIndex) })}
              >
                ×
              </Button>
            )}
          </div>
        ))}
        {!readOnly && question.options.length < 10 && (
          <button
            type="button"
            className="self-start text-sm text-app-link"
            onClick={() => onChange({ ...question, options: [...question.options, { text: '', is_correct: false }] })}
          >
            + Variant qo'shish
          </button>
        )}
      </fieldset>
      <Field label="Izoh (ixtiyoriy)" hint="Test yopilgandan keyin a'zolarga to'g'ri javob bilan birga ko'rsatiladi">
        <Input
          value={question.explanation ?? ''}
          onChange={(e) => onChange({ ...question, explanation: e.target.value || null })}
          maxLength={2000}
          disabled={readOnly}
        />
      </Field>
      {!readOnly && problems.length > 0 && <p className="text-sm text-amber-700">⚠️ {problems.join(', ')}</p>}
    </Card>
  )
}

export function TestEditorPage({ testId }: { testId: string }) {
  const { api, can } = useSession()
  const { state, reload } = useAsync((signal) => api<AdminTestDetail>(`/api/v1/admin/tests/${testId}`, { signal }), [testId])
  const [questions, setQuestions] = useState<AdminQuestion[]>([])
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (state.status === 'success' && !dirty) setQuestions(state.data.questions)
    // Only refill from the server when there are no unsaved local edits.
  }, [state])

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const test = state.data
  const locked = test.participant_count > 0
  const readOnly = locked || !can('TEST_EDIT')
  const invalid = questions.some((q) => problemsOf(q).length > 0)

  function update(next: AdminQuestion[]) {
    setQuestions(next)
    setDirty(true)
  }

  async function run(label: string, action: () => Promise<unknown>) {
    setBusy(label)
    setError(null)
    try {
      await action()
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(null)
    }
  }

  const saveQuestions = () =>
    run('save', async () => {
      await api(`/api/v1/admin/tests/${test.id}/questions`, {
        method: 'PUT',
        body: {
          questions: questions.map((q) => ({
            type: q.type,
            text: q.text.trim(),
            points: q.points,
            explanation: q.explanation?.trim() || null,
            options: q.options.map((o) => ({ text: o.text.trim(), is_correct: o.is_correct })),
          })),
        },
      })
      setDirty(false)
    })

  return (
    <>
      <PageHeader
        title={test.title}
        subtitle={`${formatDateTime(test.starts_at)} — ${formatDateTime(test.ends_at)} · ${test.question_count} ta savol · ${test.participant_count} qatnashchi`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <TestStateBadge state={test.state} />
            <Button variant="secondary" onClick={() => navigate('/tests')}>
              ← Testlar
            </Button>
            <Button variant="secondary" onClick={() => navigate(`/tests/${test.id}/results`)}>
              Natijalar
            </Button>
            {can('TEST_PUBLISH') && test.status === 'DRAFT' && (
              <Button
                loading={busy === 'publish'}
                disabled={dirty || test.question_count === 0}
                title={dirty ? 'Avval savollarni saqlang' : undefined}
                onClick={() => void run('publish', () => api(`/api/v1/admin/tests/${test.id}/publish`, { method: 'POST' }))}
              >
                📢 E'lon qilish
              </Button>
            )}
            {can('TEST_PUBLISH') && test.status === 'PUBLISHED' && !locked && (
              <Button
                variant="secondary"
                loading={busy === 'unpublish'}
                onClick={() => void run('unpublish', () => api(`/api/v1/admin/tests/${test.id}/unpublish`, { method: 'POST' }))}
              >
                Qoralamaga qaytarish
              </Button>
            )}
            {can('TEST_PUBLISH') && test.status === 'PUBLISHED' && (
              <Button
                variant="danger"
                loading={busy === 'close'}
                onClick={() => {
                  if (window.confirm("Testni hozir yopasizmi? Yechilayotgan urinishlar topshirilgan hisoblanadi va o'rinlar uchun bonus beriladi."))
                    void run('close', () => api(`/api/v1/admin/tests/${test.id}/close`, { method: 'POST' }))
                }}
              >
                Testni yopish
              </Button>
            )}
            {can('TEST_DELETE') && !locked && (
              <Button
                variant="ghost"
                className="text-app-danger"
                onClick={() => {
                  if (window.confirm("Testni o'chirasizmi?"))
                    void run('delete', async () => {
                      await api(`/api/v1/admin/tests/${test.id}`, { method: 'DELETE' })
                      navigate('/tests')
                    })
                }}
              >
                O'chirish
              </Button>
            )}
          </div>
        }
      />
      <InlineError message={error} />
      <SettingsForm key={test.id + test.status} test={test} readOnlyScores={locked} onSaved={reload} />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Savollar ({questions.length})</h2>
        {locked && (
          <p className="text-sm text-app-hint">🔒 A'zolar testni boshlagan — savollarni o'zgartirib bo'lmaydi (natijalar adolatli qolishi uchun).</p>
        )}
      </div>
      {questions.length === 0 && (
        <Card className="p-6 text-center text-sm text-app-hint">Hali savol yo'q. «+ Savol qo'shish» tugmasini bosing.</Card>
      )}
      {questions.map((question, index) => (
        <QuestionEditor
          key={question.id ?? `new-${index}`}
          index={index}
          total={questions.length}
          question={question}
          readOnly={readOnly}
          onChange={(next) => update(questions.map((q, i) => (i === index ? next : q)))}
          onMove={(delta) => {
            const next = [...questions]
            const [moved] = next.splice(index, 1)
            next.splice(index + delta, 0, moved)
            update(next)
          }}
          onRemove={() => update(questions.filter((_, i) => i !== index))}
        />
      ))}
      {!readOnly && (
        <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-between gap-2 border-t border-app-border bg-app-surface/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
          <Button variant="secondary" disabled={questions.length >= 200} onClick={() => update([...questions, blankQuestion()])}>
            + Savol qo'shish
          </Button>
          <div className="flex items-center gap-3">
            {dirty && <span className="text-sm text-amber-700">Saqlanmagan o'zgarishlar bor</span>}
            <Button loading={busy === 'save'} disabled={!dirty || invalid || questions.length === 0} onClick={() => void saveQuestions()}>
              Savollarni saqlash
            </Button>
          </div>
        </div>
      )}
    </>
  )
}
