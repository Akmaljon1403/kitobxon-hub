import { useCallback, useState } from 'react'

import { QuestionImage } from '../components/QuestionImage'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, ProgressRing, SectionTitle, Stat } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { AttemptResult, ClubTest, RunningAttempt, TestReview, TestStandings } from '../types/api'
import { formatEventDate } from '../utils/format'
import { navigate } from '../utils/router'
import { confirmAction, haptic } from '../utils/telegram'
import { TestRunner } from './TestRunner'
import { TestStateBadge } from './TestsPage'

const STATUS_LABELS = { SUBMITTED: 'Topshirildi', EXPIRED: 'Vaqt tugadi', IN_PROGRESS: 'Davom etmoqda' } as const

function ResultCard({ result, test }: { result: AttemptResult; test: ClubTest }) {
  return (
    <Card className="flex flex-col items-center gap-3 py-6 text-center">
      <ProgressRing value={result.score} max={result.max_score} size={108} stroke={9}>
        <div className="flex flex-col items-center leading-none">
          <span className="font-serif text-3xl font-bold tabular-nums">{result.score}</span>
          <span className="mt-0.5 text-xs text-app-hint">/{result.max_score}</span>
        </div>
      </ProgressRing>
      <div>
        <p className="font-serif text-lg font-bold">{result.passed ? '🎉 Tabriklaymiz!' : '📘 Yakunlandi'}</p>
        <p className="text-sm text-app-hint">
          {result.correct_count} ta to'g'ri javob ({result.question_count} tadan)
        </p>
      </div>
      {result.points_awarded > 0 && <Badge tone="success">+{result.points_awarded} ball reytingga qo'shildi</Badge>}
      {!result.passed && test.passing_score > 0 && (
        <p className="text-sm text-app-hint">Ball olish uchun kamida {test.passing_score} ball kerak edi.</p>
      )}
      <p className="mt-2 text-xs text-app-hint">
        To'g'ri javoblar test yopilgandan keyin ({formatEventDate(result.review_available_at)}) ko'rinadi.
      </p>
    </Card>
  )
}

const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }

/** The places of a closed test: everybody in order, «davomatsiz» for members who missed the event. */
function Standings({ testId }: { testId: string }) {
  const { api } = useAuth()
  const { state } = useAsync((signal) => api<TestStandings>(`/api/v1/tests/${testId}/standings`, { signal }), [testId])
  if (state.status !== 'success' || state.data.rows.length === 0) return null
  const table = state.data
  return (
    <>
      <SectionTitle>🏆 O'rinlar</SectionTitle>
      <Card className="flex flex-col gap-1.5">
        {table.rows.map((row) => (
          <div key={`${row.place}-${row.name}`} className={`flex items-center justify-between gap-2 text-sm ${row.me ? 'font-semibold' : ''}`}>
            <span className="flex min-w-0 items-center gap-1.5">
              <span className="w-7 shrink-0 text-right tabular-nums text-app-hint">{row.place}.</span>
              <span className="truncate">
                {row.prize_place ? `${MEDALS[row.prize_place]} ` : ''}
                {row.name}
                {row.me && ' (siz)'}
              </span>
              {row.attended === false && (
                <span className="shrink-0 rounded-full bg-amber-400/20 px-1.5 py-0.5 text-[10px] text-amber-700 dark:text-amber-300">
                  davomatsiz
                </span>
              )}
            </span>
            <span className="shrink-0 tabular-nums">
              {row.score}/{table.max_score}
            </span>
          </div>
        ))}
        {table.event_test && (
          <p className="mt-1 text-xs text-app-hint">
            Tadbir testi: sovrinli o'rinlar (🥇🥈🥉), sertifikat va sovg'alar faqat tadbirda davomat qilganlarga beriladi.
          </p>
        )}
      </Card>
    </>
  )
}

function Review({ testId }: { testId: string }) {
  const { api } = useAuth()
  const { state, reload } = useAsync((signal) => api<TestReview>(`/api/v1/tests/${testId}/review`, { signal }), [testId])
  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const review = state.data
  return (
    <>
      <Card className="text-center">
        <p className="text-sm text-app-hint">Eng yaxshi natijangiz</p>
        <p className="text-2xl font-bold tabular-nums">
          {review.score}/{review.max_score}
        </p>
        {review.place && (
          <p className="text-sm text-app-hint">
            {review.place}-o'rin · {review.participants} ishtirokchi
            {review.attended === false && ' · davomatsiz (sovrinli o‘rinlarga kirmaydi)'}
          </p>
        )}
      </Card>
      {review.questions.map((question, index) => (
        <Card key={question.id} className="flex flex-col gap-2">
          <p className="text-xs text-app-hint">
            {index + 1}-savol · {question.is_correct ? `✅ +${question.points_awarded}` : '❌ 0'} ball
          </p>
          <p className="whitespace-pre-line font-medium">{question.text}</p>
          {question.has_image && <QuestionImage testId={review.test_id} questionId={question.id} />}
          <ul className="flex flex-col gap-1.5">
            {question.options.map((option) => (
              <li
                key={option.id}
                className={`rounded-xl px-3 py-2 text-sm ${
                  option.is_correct
                    ? 'bg-green-500/15 text-green-700 dark:text-green-300'
                    : option.selected
                      ? 'bg-red-500/10 text-app-danger'
                      : 'bg-app-surface'
                }`}
              >
                {option.is_correct ? '✓ ' : option.selected ? '✗ ' : ''}
                {option.text}
                {option.selected && <span className="text-xs opacity-70"> — sizning javobingiz</span>}
              </li>
            ))}
          </ul>
          {question.explanation && <p className="text-sm text-app-hint">💡 {question.explanation}</p>}
        </Card>
      ))}
    </>
  )
}

function Overview({
  test,
  result,
  notice,
  onStart,
  starting,
  error,
}: {
  test: ClubTest
  result: AttemptResult | null
  notice: string | null
  onStart: () => void
  starting: boolean
  error: string | null
}) {
  const [showReview, setShowReview] = useState(false)
  const goBack = useCallback(() => navigate('/tests'), [])
  useBackButton(goBack)
  const used = test.attempts.length
  const finished = test.attempts.filter((attempt) => attempt.status !== 'IN_PROGRESS')

  return (
    <>
      <Card className="flex flex-col gap-3">
        <div className="flex flex-col items-start gap-1.5">
          <TestStateBadge test={test} />
          <h1 className="font-serif text-2xl font-bold leading-tight">{test.title}</h1>
          {test.book_title && (
            <button
              type="button"
              className="text-left text-sm font-medium text-app-link"
              onClick={() => navigate(`/books/${test.book_id}`)}
            >
              📚 {test.book_title}
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Stat label="savol" value={test.question_count} />
          {test.duration_minutes ? <Stat label="daqiqa" value={test.duration_minutes} /> : null}
          <Stat label="ballgacha" value={test.max_score} />
          <Stat label="urinish" value={`${used}/${test.attempts_allowed}`} />
        </div>
        <div className="flex flex-col gap-1 text-sm text-app-hint">
          <span>
            🗓 {formatEventDate(test.starts_at)} — {formatEventDate(test.ends_at)}
          </span>
          {test.passing_score > 0 && <span>🎯 O'tish bali: {test.passing_score} ball</span>}
        </div>
        {test.description && <p className="whitespace-pre-line pt-1 text-[15px]">{test.description}</p>}
      </Card>

      {notice && (
        <Card className="text-center text-sm">
          <p className="font-medium">⏰ {notice}</p>
        </Card>
      )}
      {result && <ResultCard result={result} test={test} />}

      {test.can_start && (
        <Card className="flex flex-col gap-2">
          {!test.in_progress && (
            <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-app-hint">
              <li>Boshlaganingizdan keyin vaqt to'xtamaydi — ilovadan chiqsangiz ham.</li>
              <li>Javoblar har bir belgilashda serverga saqlanadi.</li>
              <li>Vaqt tugasa, belgilangan javoblaringiz avtomatik topshiriladi.</li>
              <li>Boshqa ilovaga o'tishlar qayd etiladi.</li>
            </ul>
          )}
          <Button loading={starting} onClick={onStart}>
            {test.in_progress ? '▶️ Davom ettirish' : used > 0 ? '🔁 Qayta urinish' : '▶️ Testni boshlash'}
          </Button>
          {error && (
            <p role="alert" className="text-center text-sm text-app-danger">
              {error}
            </p>
          )}
        </Card>
      )}

      {test.state === 'UPCOMING' && (
        <Card className="text-center text-sm text-app-hint">Test {formatEventDate(test.starts_at)} da ochiladi.</Card>
      )}

      {finished.length > 0 && (
        <Card>
          <SectionTitle>Urinishlarim</SectionTitle>
          <ul className="flex flex-col divide-y divide-app-hint/10">
            {finished.map((attempt) => (
              <li key={attempt.attempt_number} className="flex items-center justify-between py-2 text-sm">
                <span>
                  {attempt.attempt_number}-urinish ·{' '}
                  <span className="text-app-hint">{STATUS_LABELS[attempt.status]}</span>
                </span>
                <span className="font-semibold tabular-nums">
                  {attempt.score ?? 0}/{test.max_score}
                  <span className="font-normal text-app-hint">
                    {' '}
                    · {attempt.correct_count ?? 0}/{attempt.question_count} ✓
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {test.review_available &&
        (showReview ? (
          <>
            <SectionTitle>To'g'ri javoblar</SectionTitle>
            <Review testId={test.id} />
          </>
        ) : (
          <Button variant="secondary" onClick={() => setShowReview(true)}>
            📖 To'g'ri javoblarni ko'rish
          </Button>
        ))}
      {test.state === 'CLOSED' && finished.length === 0 && (
        <Card className="text-center text-sm text-app-hint">Bu test yopilgan. Siz unda qatnashmagansiz.</Card>
      )}
      {test.state === 'CLOSED' && <Standings testId={test.id} />}
    </>
  )
}

export function TestDetailPage({ testId }: { testId: string }) {
  const { api } = useAuth()
  const { state, reload } = useAsync((signal) => api<ClubTest>(`/api/v1/tests/${testId}`, { signal }), [testId])
  const [attempt, setAttempt] = useState<RunningAttempt | null>(null)
  const [result, setResult] = useState<AttemptResult | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const finish = useCallback(
    (finishedResult: AttemptResult | null, message?: string) => {
      setAttempt(null)
      setResult(finishedResult)
      setNotice(finishedResult ? null : (message ?? 'Vaqt tugadi.'))
      reload()
    },
    [reload],
  )
  const leave = useCallback(() => {
    setAttempt(null)
    navigate('/tests')
  }, [])

  if (attempt) return <TestRunner attempt={attempt} onFinished={finish} onLeave={leave} />
  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const test = state.data

  async function start() {
    if (
      !test.in_progress &&
      !(await confirmAction(`Test boshlanadi: ${test.duration_minutes} daqiqa vaqtingiz bor. Tayyormisiz?`))
    )
      return
    setStarting(true)
    setError(null)
    try {
      const running = await api<RunningAttempt>(`/api/v1/tests/${test.id}/start`, { method: 'POST' })
      setResult(null)
      setNotice(null)
      setAttempt(running)
    } catch (err) {
      haptic('error')
      setError(err instanceof ApiError ? err.message : "Testni boshlab bo'lmadi.")
      reload()
    } finally {
      setStarting(false)
    }
  }

  return (
    <Overview test={test} result={result} notice={notice} onStart={() => void start()} starting={starting} error={error} />
  )
}
