import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, InlineError, Modal, PageHeader, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useSession } from '../store/session'
import type { AttemptDetail, TestResultRow, TestResults } from '../types/api'
import { formatDateTime, formatTime } from '../utils/format'
import { navigate } from '../utils/router'
import { TestStateBadge } from './TestsPage'

const STATUS = {
  SUBMITTED: { label: 'Topshirdi', tone: 'success' },
  EXPIRED: { label: 'Vaqt tugadi', tone: 'warning' },
  IN_PROGRESS: { label: 'Yechmoqda', tone: 'info' },
} as const
const SIGNAL_LABELS: Record<string, string> = {
  VISIBILITY_HIDDEN: 'Ilovadan chiqdi (ekran yashirildi)',
  VISIBILITY_VISIBLE: 'Ilovaga qaytdi',
  FOCUS_LOST: 'Oynadan chiqdi',
  FOCUS_GAINED: 'Oynaga qaytdi',
  LEFT_TEST: 'Testdan chiqib ketdi',
  RETURNED: 'Testga qaytdi',
  RECONNECTED: 'Testni qayta ochdi',
  TIMEOUT: 'Vaqt tugadi',
  FAST_ANSWER: 'Juda tez javob berdi',
  OTHER: 'Boshqa',
}

function duration(seconds: number | null): string {
  if (seconds == null) return '—'
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

function AttemptModal({ row, onClose }: { row: TestResultRow; onClose: () => void }) {
  const { api } = useSession()
  const { state, reload } = useAsync(
    (signal) => api<AttemptDetail>(`/api/v1/admin/test-attempts/${row.attempt_id}`, { signal }),
    [row.attempt_id],
  )
  return (
    <Modal title={`${row.last_name} ${row.first_name} — ${row.attempt_number}-urinish`} onClose={onClose} wide>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <>
          <p className="text-sm text-app-hint">
            Boshladi: {formatDateTime(state.data.started_at)} · Muddat: {formatTime(state.data.deadline_at)} · Tugatdi:{' '}
            {formatDateTime(state.data.submitted_at)}
          </p>
          <ol className="flex flex-col gap-2">
            {state.data.answers.map((answer, index) => (
              <li key={index} className="rounded-lg border border-app-border p-3 text-sm">
                <p className="font-medium">
                  {answer.is_correct ? '✅' : '❌'} {index + 1}. {answer.question}
                </p>
                <p className="text-app-hint">
                  Javobi: {answer.selected.length ? answer.selected.join(', ') : '— javob bermagan'}
                  {!answer.is_correct && ` · To'g'ri: ${answer.correct.join(', ')}`}
                </p>
              </li>
            ))}
          </ol>
          <div>
            <h3 className="mb-1 font-semibold">Faollik signallari</h3>
            <p className="mb-2 text-xs text-app-hint">
              Bu signallar faqat ishora — isbot emas. Masalan, qo'ng'iroq kelsa ham ilova yashiriladi.
            </p>
            {state.data.activity.length === 0 ? (
              <p className="text-sm text-app-hint">Signal qayd etilmagan.</p>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {state.data.activity.map((item, index) => (
                  <li key={index}>
                    <span className="tabular-nums text-app-hint">{formatTime(item.at)}</span> — {SIGNAL_LABELS[item.type] ?? item.type}
                    {item.details?.seconds_away != null && ` (${String(item.details.seconds_away)} soniya)`}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </Modal>
  )
}

export function TestResultsPage({ testId }: { testId: string }) {
  const { api, can } = useSession()
  const { state, reload } = useAsync((signal) => api<TestResults>(`/api/v1/admin/tests/${testId}/results`, { signal }), [testId])
  const [selected, setSelected] = useState<TestResultRow | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function download(title: string) {
    const token = sessionStorage.getItem('kitobxon.admin.token')
    const response = await fetch(`/api/v1/admin/tests/${testId}/results.csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) {
      setError("Faylni yuklab bo'lmadi.")
      return
    }
    const link = document.createElement('a')
    link.href = URL.createObjectURL(await response.blob())
    link.download = `test_${title}.csv`
    link.click()
    URL.revokeObjectURL(link.href)
  }

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const { test, items } = state.data

  return (
    <>
      <PageHeader
        title={`Natijalar: ${test.title}`}
        subtitle="Tartib: ball → tezroq yechgan → oldinroq topshirgan. Bonuslar test yopilgach beriladi."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <TestStateBadge state={test.state} />
            <Button variant="secondary" onClick={() => navigate(can('TEST_VIEW') ? `/tests/${test.id}` : '/tests')}>
              Savollar
            </Button>
            <Button variant="secondary" onClick={reload}>
              ↻ Yangilash
            </Button>
            <Button variant="secondary" onClick={() => void download(test.title)}>
              ⬇ Excel (CSV)
            </Button>
          </div>
        }
      />
      <InlineError message={error} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ['Qatnashchilar', state.data.participants],
          ["O'tganlar", state.data.passed],
          ["O'rtacha ball", state.data.average_score ?? '—'],
          ['Maksimal ball', test.max_score],
        ].map(([label, value]) => (
          <Card key={label} className="p-4">
            <p className="text-sm text-app-hint">{label}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
          </Card>
        ))}
      </div>
      <Card>
        <Table head={["O'rin", "A'zo", 'Urinish', 'Holat', "To'g'ri", 'Ball', 'Vaqt', 'Signallar', '']}>
          {items.length === 0 && <EmptyRow colSpan={9} text="Hali hech kim qatnashmagan" />}
          {items.map((row) => (
            <tr key={row.attempt_id}>
              <td className="px-4 py-2 tabular-nums">
                {row.place ? `${row.place}.` : '—'}
                {row.attended === false && (
                  <span title="Tadbirda davomat qilmagan: sovrinli o'rinlar va sovg'alar hisobiga kirmaydi">
                    {' '}
                    <Badge tone="warning">davomatsiz</Badge>
                  </span>
                )}
                {row.prize_place && row.prize_place <= 3 && row.attended !== null && row.attended !== undefined && (
                  <p className="text-xs text-app-hint">sovrinli: {row.prize_place}-o'rin</p>
                )}
              </td>
              <td className="px-4 py-2">
                <p className="font-medium">
                  {row.last_name} {row.first_name}
                </p>
                <p className="text-xs text-app-hint">
                  {row.faculty ?? ''} {row.group_name ? `· ${row.group_name}` : ''}
                </p>
              </td>
              <td className="px-4 py-2 tabular-nums">{row.attempt_number}</td>
              <td className="px-4 py-2">
                <Badge tone={STATUS[row.status].tone}>{STATUS[row.status].label}</Badge>
              </td>
              <td className="px-4 py-2 tabular-nums">
                {row.correct_count ?? 0}/{row.question_count}
              </td>
              <td className="px-4 py-2 font-semibold tabular-nums">
                {row.score ?? '—'}
                {row.passed === false && <span className="ml-1 text-xs font-normal text-app-hint">(o'tmadi)</span>}
              </td>
              <td className="px-4 py-2 tabular-nums">{duration(row.duration_seconds)}</td>
              <td className="px-4 py-2">
                {row.signals > 0 ? <Badge tone="warning">⚠ {row.signals}</Badge> : <span className="text-app-hint">—</span>}
              </td>
              <td className="px-4 py-2 text-right">
                <Button variant="ghost" onClick={() => setSelected(row)}>
                  Batafsil
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      </Card>
      {selected && <AttemptModal row={selected} onClose={() => setSelected(null)} />}
    </>
  )
}
