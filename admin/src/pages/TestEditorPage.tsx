import { useEffect, useRef, useState } from 'react'

import { CertificateDesignBox } from '../components/CertificateDesign'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, Field, InlineError, Input, PageHeader, Select, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminQuestion, AdminTestDetail, Book, Page, QuestionImport, QuestionType } from '../types/api'
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
  const designs = useAsync((signal) =>
    api<{ id: string; name: string; is_default: boolean }[]>('/api/v1/admin/certificate-templates', { signal }),
  )
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
    questions_per_attempt: test.questions_per_attempt ? String(test.questions_per_attempt) : '',
    certificate_template_id: test.certificate_template_id ?? '',
    certificate_on_pass: test.certificate_on_pass,
  }
  const [form, setForm] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const editable = can('TEST_EDIT')
  const permanent = test.kind === 'PERMANENT'  // «Doimiy»: no window / admin score — the server manages those
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
          duration_minutes: Number(form.duration_minutes),
          shuffle_questions: form.shuffle_questions,
          shuffle_options: form.shuffle_options,
          questions_per_attempt: form.questions_per_attempt ? Number(form.questions_per_attempt) : null,
          certificate_template_id: form.certificate_template_id || null,
          certificate_on_pass: form.certificate_on_pass,
          // A permanent («Doimiy») test's window, score and attempt limit are managed by the server.
          ...(permanent
            ? {}
            : {
                starts_at: fromLocalInput(form.starts_at),
                ends_at: fromLocalInput(form.ends_at),
                max_score: Number(form.max_score),
                passing_score: Number(form.passing_score),
                attempts_allowed: Number(form.attempts_allowed),
              }),
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
      {permanent && (
        <p className="rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-200">
          📌 Bu <b>Doimiy test</b>: doim ochiq turadi, a'zo cheksiz marta yechadi va faqat birinchi marta 100% yechsa
          ball oladi. Shuning uchun vaqt oynasi, maksimal ball va urinishlar soni bu yerda sozlanmaydi.
        </p>
      )}
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
        {!permanent && (
          <Field label="Ochiladi (Toshkent vaqti)">
            <Input type="datetime-local" value={form.starts_at} onChange={set('starts_at')} disabled={!editable} />
          </Field>
        )}
        {!permanent && (
          <Field label="Yopiladi" hint="Yopilgach to'g'ri javoblar ochiladi va o'rinlar uchun bonus beriladi">
            <Input type="datetime-local" value={form.ends_at} onChange={set('ends_at')} disabled={!editable} />
          </Field>
        )}
        <Field label="Yechish vaqti (daqiqa)">
          <Input type="number" min={1} max={600} value={form.duration_minutes} onChange={set('duration_minutes')} disabled={!editable} />
        </Field>
        {!permanent && (
          <Field label="Urinishlar soni" hint="Bir nechta bo'lsa, eng yaxshi natija hisoblanadi">
            <Input type="number" min={1} max={10} value={form.attempts_allowed} onChange={set('attempts_allowed')} disabled={!editable} />
          </Field>
        )}
        {!permanent && (
          <Field label="Maksimal ball" hint={readOnlyScores ? 'Test boshlangan — o\'zgartirib bo\'lmaydi' : 'Reytingga qo\'shiladigan eng yuqori ball'}>
            <Input type="number" min={1} max={1000} value={form.max_score} onChange={set('max_score')} disabled={!editable || readOnlyScores} />
          </Field>
        )}
        {!permanent && (
          <Field label="O'tish bali" hint="Bundan kam natija ball bermaydi (0 — chegarasiz)">
            <Input type="number" min={0} max={1000} value={form.passing_score} onChange={set('passing_score')} disabled={!editable || readOnlyScores} />
          </Field>
        )}
        <Field
          label="Har bir a'zoga nechta savol"
          hint={
            readOnlyScores
              ? "Test boshlangan — o'zgartirib bo'lmaydi"
              : `Bazada ${test.question_count} ta savol. Bo'sh qoldirilsa — hammasi; son yozilsa, har bir a'zoga shuncha savol tasodifiy tanlanadi`
          }
        >
          <Input
            type="number"
            min={1}
            max={Math.max(1, test.question_count)}
            placeholder={`Hammasi (${test.question_count})`}
            value={form.questions_per_attempt}
            onChange={set('questions_per_attempt')}
            disabled={!editable || readOnlyScores}
          />
        </Field>
      </div>
      {form.questions_per_attempt && Number(form.questions_per_attempt) < test.question_count && (
        <p className="rounded-lg bg-indigo-50 px-3 py-2 text-sm text-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-200">
          🎲 Har bir a'zo {test.question_count} ta savoldan tasodifiy <b>{form.questions_per_attempt}</b> tasini oladi —
          yonidagi talabaning savollari boshqacha bo'ladi. Ball savollar soniga emas, to'g'ri javoblar ulushiga qarab
          hisoblanadi, shuning uchun hamma teng sharoitda. Qayta urinishda avval ko'rmagan savollari beriladi.
        </p>
      )}
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
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Sertifikat dizayni" hint="G'oliblarga shu dizaynda beriladi. Bo'sh — asosiy/standart dizayn">
          <Select value={form.certificate_template_id} onChange={set('certificate_template_id')} disabled={!editable}>
            <option value="">— Asosiy / standart —</option>
            {designs.state.status === 'success' &&
              designs.state.data.map((design) => (
                <option key={design.id} value={design.id}>
                  {design.name}
                  {design.is_default ? ' (asosiy)' : ''}
                </option>
              ))}
          </Select>
        </Field>
        <label className="flex items-start gap-2 pt-7 text-sm">
          <input
            type="checkbox"
            checked={form.certificate_on_pass}
            disabled={!editable}
            onChange={(e) => {
              setSaved(false)
              setForm({ ...form, certificate_on_pass: e.target.checked })
            }}
          />
          <span>
            Testdan o'tgan <b>har bir</b> a'zoga ishtirok sertifikati (faqat 1–3 o'rin emas)
          </span>
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

/** A question's picture: shown from storage, replaced or removed (saved with the questions). */
function QuestionImage({
  testId,
  imageKey,
  readOnly,
  onChange,
}: {
  testId: string
  imageKey: string | null | undefined
  readOnly: boolean
  onChange: (key: string | null) => void
}) {
  const { api, download } = useSession()
  const [src, setSrc] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!imageKey) {
      setSrc(null)
      return
    }
    let url: string | null = null
    let cancelled = false
    download(`/api/v1/admin/tests/${testId}/question-images?key=${encodeURIComponent(imageKey)}`)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => setSrc(null))
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [download, imageKey, testId])

  async function upload(file: File | undefined) {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const result = await api<{ image_key: string }>(`/api/v1/admin/tests/${testId}/question-images`, { method: 'POST', body: form })
      onChange(result.image_key)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Rasmni yuklab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  if (readOnly && !imageKey) return null
  return (
    <div className="flex flex-wrap items-start gap-3">
      {src && <img src={src} alt="Savol rasmi" className="max-h-48 rounded-lg border border-app-border" />}
      {!readOnly && (
        <div className="flex flex-col gap-1">
          <input ref={input} type="file" accept="image/*" className="hidden" onChange={(e) => void upload(e.target.files?.[0])} />
          <Button variant="secondary" loading={busy} onClick={() => input.current?.click()}>
            🖼 {imageKey ? 'Rasmni almashtirish' : "Rasm qo'shish"}
          </Button>
          {imageKey && (
            <Button variant="ghost" className="text-app-danger" onClick={() => onChange(null)}>
              Rasmni olib tashlash
            </Button>
          )}
          <InlineError message={error} />
        </div>
      )}
    </div>
  )
}

function QuestionEditor({
  testId,
  index,
  question,
  total,
  readOnly,
  onChange,
  onMove,
  onRemove,
}: {
  testId: string
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
      <QuestionImage testId={testId} imageKey={question.image_key} readOnly={readOnly} onChange={(key) => onChange({ ...question, image_key: key })} />
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
  const [warnings, setWarnings] = useState<string[]>([])
  const importInput = useRef<HTMLInputElement>(null)

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

  async function importFile(file: File | undefined) {
    if (!file) return
    setBusy('import')
    setError(null)
    setWarnings([])
    try {
      const form = new FormData()
      form.append('file', file)
      const result = await api<QuestionImport>(`/api/v1/admin/tests/${test.id}/import`, { method: 'POST', body: form })
      const replace =
        questions.length === 0 ||
        window.confirm(
          `Fayldan ${result.questions.length} ta savol o'qildi.\n\nOK — hozirgi ${questions.length} ta savol o'rniga qo'yiladi.\nBekor qilish — oxiriga qo'shiladi.`,
        )
      update((replace ? result.questions : [...questions, ...result.questions]).slice(0, 500))
      setWarnings(result.warnings)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Faylni o'qib bo'lmadi.")
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
            image_key: q.image_key ?? null,
          })),
        },
      })
      setDirty(false)
    })

  return (
    <>
      <PageHeader
        title={test.title}
        subtitle={`${test.kind === 'PERMANENT' ? 'Doimiy test — doim ochiq' : `${formatDateTime(test.starts_at)} — ${formatDateTime(test.ends_at)}`} · ${test.question_count} ta savol${test.questions_per_attempt && test.questions_per_attempt < test.question_count ? ` (har a'zoga ${test.questions_per_attempt} ta tasodifiy)` : ''} · ${test.participant_count} qatnashchi`}
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
      {/* Settings were set when the test was created — tuck them away so the editor opens straight to the
          questions (the test-building part). The owner opens this only to change dates, time or scoring. */}
      <details className="rounded-xl border border-app-border bg-app-bg">
        <summary className="cursor-pointer px-4 py-3 font-medium">⚙️ Test sozlamalari va sertifikat dizayni</summary>
        <div className="flex flex-col gap-3 border-t border-app-border p-3">
          <SettingsForm key={test.id + test.status} test={test} readOnlyScores={locked} onSaved={reload} />
          {can('TEST_EDIT') && (
            <Card className="p-4">
              {test.event_id && !test.certificate_background && (
                <p className="mb-2 text-xs text-app-hint">Test tadbirga bog'langan: bu yerda rasm yuklanmasa, tadbirning sertifikat dizayni ishlatiladi.</p>
              )}
              <CertificateDesignBox base={`/api/v1/admin/tests/${test.id}`} hasBackground={test.certificate_background} onChanged={reload} />
            </Card>
          )}
        </div>
      </details>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Savollar ({questions.length})</h2>
        {!readOnly && (
          <>
            <input
              ref={importInput}
              type="file"
              accept=".txt,.docx,.pdf,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="hidden"
              onChange={(e) => {
                void importFile(e.target.files?.[0])
                e.target.value = ''
              }}
            />
            <Button variant="secondary" loading={busy === 'import'} onClick={() => importInput.current?.click()}>
              📥 Fayldan yuklash (TXT, Word, PDF)
            </Button>
          </>
        )}
        {locked && (
          <p className="text-sm text-app-hint">🔒 A'zolar testni boshlagan — savollarni o'zgartirib bo'lmaydi (natijalar adolatli qolishi uchun).</p>
        )}
      </div>
      {warnings.length > 0 && (
        <Card className="border-amber-400 p-4 text-sm">
          <p className="mb-1 font-medium">⚠️ Fayl o'qildi — tekshirib chiqing:</p>
          <ul className="list-disc pl-5">
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </Card>
      )}
      {!readOnly && (
        <details className="rounded-xl border border-app-border p-3 text-sm">
          <summary className="cursor-pointer font-medium">📄 Fayl qanday tayyorlanadi?</summary>
          <pre className="mt-2 whitespace-pre-wrap rounded bg-app-surface p-3 text-xs">{`1. «O'tkan kunlar» romani muallifi kim? (2 ball)
A) Cho'lpon
*B) Abdulla Qodiriy
C) Oybek
Izoh: Roman 1922–1925-yillarda yozilgan.

2. Qaysilari shoir?
A) Navoiy
B) Bobur
C) Qodiriy
Javob: A, B`}</pre>
          <ul className="mt-2 list-disc pl-5 text-app-hint">
            <li>Savol raqam bilan boshlanadi («1.» yoki «1)»), variantlar — «A)», «B.» ...</li>
            <li>To'g'ri javob: oldiga yoki oxiriga «*» («+», «#»), yoki «Javob: B» qatori; Word'da qalin (bold) yozilsa ham bo'ladi.</li>
            <li>«Izoh: ...» — test yopilgach ko'rinadigan tushuntirish; «(2 ball)» — savol bali.</li>
            <li>Word yoki PDF'da savol tagidagi rasm o'sha savolga biriktiriladi.</li>
            <li>Savollar avval tahrirlovchida ko'rinadi — tekshirib, «Savollarni saqlash»ni bosing.</li>
          </ul>
        </details>
      )}
      {questions.length === 0 && (
        <Card className="p-6 text-center text-sm text-app-hint">Hali savol yo'q. «+ Savol qo'shish» yoki «📥 Fayldan yuklash» tugmasini bosing.</Card>
      )}
      {questions.map((question, index) => (
        <QuestionEditor
          key={question.id ?? `new-${index}`}
          testId={test.id}
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
          <Button variant="secondary" disabled={questions.length >= 500} onClick={() => update([...questions, blankQuestion()])}>
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
