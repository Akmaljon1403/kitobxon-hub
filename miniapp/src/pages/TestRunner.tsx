import { useCallback, useEffect, useRef, useState } from 'react'

import { Button } from '../components/ui'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { AttemptResult, RunningAttempt } from '../types/api'
import { confirmAction, getWebApp, haptic } from '../utils/telegram'

type Signal = { type: string; client_time: string; details?: Record<string, unknown> }

function formatClock(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

/** Sends focus/visibility signals in small batches. They are hints for the admin, never proof. */
function useActivitySignals(testId: string) {
  const { api } = useAuth()
  const queue = useRef<Signal[]>([])

  const flush = useCallback(() => {
    if (queue.current.length === 0) return
    const events = queue.current.splice(0, 30)
    void api(`/api/v1/tests/${testId}/activity`, { method: 'POST', body: { events } }).catch(() => undefined)
  }, [api, testId])

  const push = useCallback((type: string, details?: Record<string, unknown>) => {
    queue.current.push({ type, client_time: new Date().toISOString(), ...(details ? { details } : {}) })
  }, [])

  useEffect(() => {
    let hiddenAt = 0
    const onVisibility = () => {
      if (document.hidden) {
        hiddenAt = Date.now()
        push('VISIBILITY_HIDDEN')
        flush()
      } else {
        push('VISIBILITY_VISIBLE', hiddenAt ? { seconds_away: Math.round((Date.now() - hiddenAt) / 1000) } : undefined)
        flush()
      }
    }
    const onBlur = () => push('FOCUS_LOST')
    const onFocus = () => push('FOCUS_GAINED')
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('blur', onBlur)
    window.addEventListener('focus', onFocus)
    const timer = window.setInterval(flush, 5000)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
      window.removeEventListener('focus', onFocus)
      window.clearInterval(timer)
      flush()
    }
  }, [flush, push])

  return { push, flush }
}

export function TestRunner({
  attempt,
  onFinished,
  onLeave,
}: {
  attempt: RunningAttempt
  onFinished: (result: AttemptResult | null, message?: string) => void
  onLeave: () => void
}) {
  const { api } = useAuth()
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string[]>>(attempt.answers)
  const [unsaved, setUnsaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // The server clock decides: remember how far this phone's clock is from the server's.
  const offset = useRef(new Date(attempt.server_now).getTime() - Date.now())
  const deadline = new Date(attempt.deadline_at).getTime()
  const [remaining, setRemaining] = useState(deadline - (Date.now() + offset.current))
  const finished = useRef(false)
  const answersRef = useRef(answers)
  answersRef.current = answers
  const { push, flush } = useActivitySignals(attempt.test_id)

  const question = attempt.questions[index]
  const answeredCount = attempt.questions.filter((q) => (answers[q.id] ?? []).length > 0).length

  const submit = useCallback(
    async (automatic: boolean) => {
      if (finished.current) return
      if (!automatic) {
        const missing = attempt.questions.length - answeredCount
        const message = missing
          ? `${missing} ta savolga javob berilmagan. Testni yakunlaysizmi?`
          : 'Testni yakunlaysizmi? Keyin javoblarni o\'zgartirib bo\'lmaydi.'
        if (!(await confirmAction(message))) return
      }
      finished.current = true
      setSubmitting(true)
      setError(null)
      try {
        const result = await api<AttemptResult>(`/api/v1/tests/${attempt.test_id}/submit`, {
          method: 'POST',
          body: {
            answers: Object.entries(answersRef.current).map(([question_id, option_ids]) => ({ question_id, option_ids })),
          },
        })
        haptic('success')
        onFinished(result)
      } catch (err) {
        if (err instanceof ApiError && err.code === 'TEST_TIME_EXPIRED') {
          haptic('warning')
          onFinished(null, err.message)
          return
        }
        finished.current = false
        haptic('error')
        setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi. Internetni tekshirib, qayta urining.")
      } finally {
        setSubmitting(false)
      }
    },
    [api, attempt.questions.length, attempt.test_id, answeredCount, onFinished],
  )

  useEffect(() => {
    const timer = window.setInterval(() => {
      const left = deadline - (Date.now() + offset.current)
      setRemaining(left)
      if (left <= 0) void submit(true)
    }, 500)
    return () => window.clearInterval(timer)
  }, [deadline, submit])

  useEffect(() => {
    const webApp = getWebApp()
    webApp?.enableClosingConfirmation?.()
    return () => webApp?.disableClosingConfirmation?.()
  }, [])

  const leave = useCallback(async () => {
    if (!(await confirmAction("Testdan chiqasizmi? Vaqt to'xtamaydi, belgilagan javoblaringiz saqlangan."))) return
    push('LEFT_TEST')
    flush()
    onLeave()
  }, [flush, onLeave, push])
  useBackButton(leave)

  async function choose(optionId: string) {
    if (submitting || finished.current) return
    const current = answers[question.id] ?? []
    const next =
      question.type === 'SINGLE_CHOICE'
        ? [optionId]
        : current.includes(optionId)
          ? current.filter((id) => id !== optionId)
          : [...current, optionId]
    setAnswers((previous) => ({ ...previous, [question.id]: next }))
    getWebApp()?.HapticFeedback?.selectionChanged()
    try {
      await api(`/api/v1/tests/${attempt.test_id}/answer`, {
        method: 'POST',
        body: { question_id: question.id, option_ids: next },
      })
      setUnsaved(false)
    } catch (err) {
      if (err instanceof ApiError && err.code === 'TEST_TIME_EXPIRED') {
        finished.current = true
        onFinished(null, err.message)
        return
      }
      // Kept locally and sent again with the final submission.
      setUnsaved(true)
    }
  }

  const lowTime = remaining < 60_000
  const selected = answers[question.id] ?? []
  const isLast = index === attempt.questions.length - 1

  return (
    <div className="fixed inset-0 z-20 flex flex-col overflow-y-auto bg-app-surface">
      <header className="sticky top-0 z-10 border-b border-app-hint/15 bg-app-bg/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-lg items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{attempt.title}</p>
            <p className="text-xs text-app-hint">
              {index + 1}/{attempt.questions.length}-savol · {answeredCount} ta javob
            </p>
          </div>
          <span
            role="timer"
            aria-label="Qolgan vaqt"
            className={`rounded-xl px-3 py-1.5 font-mono text-lg font-semibold tabular-nums ${
              lowTime ? 'bg-red-500/15 text-app-danger' : 'bg-app-surface'
            }`}
          >
            ⏱ {formatClock(remaining)}
          </span>
        </div>
        <div className="mx-auto mt-2 h-1.5 max-w-lg rounded-full bg-app-surface">
          <div
            className="h-1.5 rounded-full bg-app-button transition-all"
            style={{ width: `${((index + 1) / attempt.questions.length) * 100}%` }}
          />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-3 p-3">
        <section className="rounded-2xl bg-app-bg p-4 shadow-sm">
          <p className="text-xs text-app-hint">
            {question.type === 'MULTIPLE_CHOICE' ? 'Bir nechta javobni belgilang' : 'Bitta javobni tanlang'} ·{' '}
            {question.points} ball
          </p>
          <h2 className="mt-1 whitespace-pre-line text-[17px] font-semibold leading-snug">{question.text}</h2>
        </section>

        <div
          className="flex flex-col gap-2"
          role={question.type === 'SINGLE_CHOICE' ? 'radiogroup' : 'group'}
          aria-label="Javob variantlari"
        >
          {question.options.map((option, optionIndex) => {
            const active = selected.includes(option.id)
            return (
              <button
                key={option.id}
                type="button"
                role={question.type === 'SINGLE_CHOICE' ? 'radio' : 'checkbox'}
                aria-checked={active}
                onClick={() => void choose(option.id)}
                className={`flex items-start gap-3 rounded-2xl border-2 bg-app-bg p-3.5 text-left text-[15px] transition-colors ${
                  active ? 'border-app-button' : 'border-transparent'
                }`}
              >
                <span
                  aria-hidden
                  className={`flex size-7 shrink-0 items-center justify-center text-sm font-semibold ${
                    question.type === 'SINGLE_CHOICE' ? 'rounded-full' : 'rounded-lg'
                  } ${active ? 'bg-app-button text-app-button-text' : 'bg-app-surface text-app-hint'}`}
                >
                  {active ? '✓' : String.fromCharCode(65 + optionIndex)}
                </span>
                <span className="pt-0.5">{option.text}</span>
              </button>
            )
          })}
        </div>

        <nav aria-label="Savollar" className="flex flex-wrap justify-center gap-1.5 pt-1">
          {attempt.questions.map((q, i) => {
            const done = (answers[q.id] ?? []).length > 0
            return (
              <button
                key={q.id}
                type="button"
                aria-label={`${i + 1}-savol${done ? ', javob berilgan' : ''}`}
                aria-current={i === index ? 'step' : undefined}
                onClick={() => setIndex(i)}
                className={`size-8 rounded-lg text-xs font-medium tabular-nums ${
                  i === index
                    ? 'bg-app-button text-app-button-text'
                    : done
                      ? 'bg-app-button/20 text-app-text'
                      : 'bg-app-bg text-app-hint'
                }`}
              >
                {i + 1}
              </button>
            )
          })}
        </nav>
        {unsaved && (
          <p className="text-center text-xs text-amber-600">
            Internet sekin: javob telefoningizda saqlandi va yakunlashda yuboriladi.
          </p>
        )}
        {error && (
          <p role="alert" className="text-center text-sm text-app-danger">
            {error}
          </p>
        )}
      </main>

      <footer
        className="sticky bottom-0 border-t border-app-hint/15 bg-app-bg/95 p-3 backdrop-blur"
        style={{ paddingBottom: 'calc(0.75rem + var(--tg-safe-area-inset-bottom, 0px))' }}
      >
        <div className="mx-auto grid max-w-lg grid-cols-2 gap-2">
          <Button variant="secondary" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
            ← Oldingi
          </Button>
          {isLast ? (
            <Button loading={submitting} onClick={() => void submit(false)}>
              Yakunlash ✓
            </Button>
          ) : (
            <Button onClick={() => setIndex((i) => i + 1)}>Keyingi →</Button>
          )}
        </div>
        {!isLast && (
          <button
            type="button"
            className="mx-auto mt-2 block text-sm text-app-link"
            disabled={submitting}
            onClick={() => void submit(false)}
          >
            Testni yakunlash
          </button>
        )}
      </footer>
    </div>
  )
}
