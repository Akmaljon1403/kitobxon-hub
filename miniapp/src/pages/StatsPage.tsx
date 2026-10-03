import { useCallback, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { useAuth } from '../store/auth'
import type { PersonalStats } from '../types/api'
import { navigate } from '../utils/router'

const CATEGORIES: Record<string, string> = {
  ATTENDANCE: '✅ Davomat',
  TEST: '📝 Testlar',
  TEST_RANK_BONUS: "🏅 Test o'rinlari",
  BOOK_COMPLETION: '📚 Kitoblar',
  MANUAL: "✍️ Admin qo'shgan",
  ACHIEVEMENT: '🏆 Yutuqlar',
}

function Tile({ value, label, hint }: { value: string; label: string; hint?: string }) {
  return (
    <Card className="flex flex-col gap-0.5 py-3">
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      <span className="text-xs text-app-hint">{label}</span>
      {hint && <span className="text-xs text-app-link">{hint}</span>}
    </Card>
  )
}

/** Points per month: one series, so no legend; tap a bar to see its value. */
function MonthlyPoints({ months }: { months: PersonalStats['months'] }) {
  const [active, setActive] = useState(months.length - 1)
  const max = Math.max(...months.map((m) => m.points), 1)
  const current = months[active]
  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <h2 className="font-semibold">Oylar bo'yicha ballar</h2>
        <span className="text-sm text-app-hint">
          {current.label}: <b className="text-app-text tabular-nums">{current.points}</b>
        </span>
      </div>
      <div className="flex h-36 items-end gap-0.5 border-b border-app-hint/20" role="list" aria-label="Oylar bo'yicha ballar">
        {months.map((month, index) => (
          <button
            key={month.month}
            type="button"
            role="listitem"
            aria-label={`${month.label}: ${month.points} ball`}
            onClick={() => setActive(index)}
            className="flex h-full flex-1 flex-col justify-end px-1.5"
          >
            <span
              className={`block w-full rounded-t ${index === active ? 'bg-app-button' : 'bg-app-button/45'}`}
              style={{ height: `${Math.max((month.points / max) * 100, month.points > 0 ? 3 : 0)}%` }}
            />
          </button>
        ))}
      </div>
      {months.every((month) => month.points === 0) && (
        <p className="text-center text-sm text-app-hint">Hozircha ball yo'q — tadbirga keling yoki test yeching, grafik o'sib boradi.</p>
      )}
      <div className="flex gap-0.5">
        {months.map((month, index) => (
          <span key={month.month} className={`flex-1 text-center text-xs ${index === active ? 'font-semibold' : 'text-app-hint'}`}>
            {month.label}
          </span>
        ))}
      </div>
    </Card>
  )
}

/** «📈 Statistikam» — a premium perk by default (the super admin decides). */
export function StatsPage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/results'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<PersonalStats>('/api/v1/me/stats', { signal }))

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const stats = state.data
  const change =
    stats.month_rank && stats.last_month_rank
      ? stats.last_month_rank - stats.month_rank
      : null
  const places = ['1', '2', '3'].map((place) => stats.test_places[place] ?? 0)

  return (
    <div className="flex flex-col gap-3">
      <h1 className="px-1 text-xl font-semibold">📈 Statistikam</h1>
      <div className="grid grid-cols-2 gap-2">
        <Tile value={String(stats.total)} label="jami ball" />
        <Tile
          value={stats.month_rank ? `${stats.month_rank}-o'rin` : '—'}
          label="shu oy reytingda"
          hint={change ? (change > 0 ? `▲ ${change} pog'ona yuqoriladi` : `▼ ${-change} pog'ona pastladi`) : undefined}
        />
        <Tile
          value={stats.attendance_rate !== null ? `${stats.attendance_rate}%` : '—'}
          label={`davomat (${stats.events_attended}/${stats.events_held} tadbir)`}
        />
        <Tile
          value={stats.tests_average_percent !== null ? `${stats.tests_average_percent}%` : '—'}
          label={`testlarda o'rtacha (${stats.tests_taken} ta)`}
        />
      </div>

      <MonthlyPoints months={stats.months} />

      <SectionTitle>Ballar qayerdan</SectionTitle>
      <Card className="flex flex-col gap-2 text-[15px]">
        {Object.entries(stats.breakdown).length === 0 && <p className="text-sm text-app-hint">Hozircha ball yo'q.</p>}
        {Object.entries(stats.breakdown)
          .sort((a, b) => b[1] - a[1])
          .map(([category, points]) => (
            <div key={category} className="flex justify-between gap-3">
              <span>{CATEGORIES[category] ?? category}</span>
              <span className="font-semibold tabular-nums">{points}</span>
            </div>
          ))}
      </Card>

      <SectionTitle>Yutuqlar</SectionTitle>
      <div className="grid grid-cols-3 gap-2 text-center">
        <Tile value={String(stats.books_completed)} label="kitob o'qildi" />
        <Tile value={String(stats.streak_weeks)} label="hafta ketma-ket faol" />
        <Tile value={String(stats.member_days)} label="kun klubda" />
      </div>
      <Card className="flex justify-around py-3 text-center text-sm">
        {['🥇', '🥈', '🥉'].map((medal, index) => (
          <span key={medal}>
            <span className="text-2xl">{medal}</span>
            <br />
            <b className="tabular-nums">{places[index]}</b> marta
          </span>
        ))}
      </Card>
      <p className="px-2 text-center text-xs text-app-hint">Test o'rinlari — testlarda egallagan 1-, 2-, 3-o'rinlaringiz soni.</p>
    </div>
  )
}
