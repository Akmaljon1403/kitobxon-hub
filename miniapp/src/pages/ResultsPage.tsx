import { useState } from 'react'

import { BottomSheet } from '../components/BottomSheet'
import { useFeature } from '../components/FeatureGate'
import { Icon, type IconName } from '../components/Icon'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Card, PageTitle, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useHomeBackButton } from '../hooks/useBackButton'
import { useAuth } from '../store/auth'
import type { MyRanking, MyScores, ScoreEntry } from '../types/api'
import { formatDate, formatTime } from '../utils/format'
import { navigate } from '../utils/router'

type Tone = 'brand' | 'gold' | 'green' | 'hint'

/** Each points category: a dimensional icon, a human label and a colour family — so every entry
 * reads at a glance and the detail view can explain exactly why the points were given. */
const CATEGORY_META: Record<string, { icon: IconName; label: string; tone: Tone }> = {
  ATTENDANCE: { icon: 'calendar', label: 'Tadbirda qatnashish', tone: 'green' },
  TEST: { icon: 'file-text', label: 'Test', tone: 'brand' },
  TEST_RANK_BONUS: { icon: 'medal', label: "Testda sovrinli o'rin", tone: 'gold' },
  BOOK_COMPLETION: { icon: 'book', label: "Kitobni o'qib tugatish", tone: 'brand' },
  CAMPAIGN: { icon: 'sparkles', label: 'Kitobxonlik kampaniyasi', tone: 'brand' },
  ACHIEVEMENT: { icon: 'trophy', label: 'Yutuq', tone: 'gold' },
  MANUAL: { icon: 'pencil', label: 'Admin tuzatishi', tone: 'hint' },
  REVERSAL: { icon: 'refresh', label: 'Bekor qilindi', tone: 'hint' },
}

function metaFor(category: string): { icon: IconName; label: string; tone: Tone } {
  return CATEGORY_META[category] ?? { icon: 'bar-chart', label: category, tone: 'hint' }
}

/** Dimensional tile: a soft gradient chip that carries the category icon (the «3D-ish» look). */
const TONE_TILE: Record<Tone, string> = {
  brand: 'bg-gradient-to-br from-brand-400/25 to-brand-600/10 text-brand-600 ring-1 ring-brand-500/15 dark:text-brand-300',
  gold: 'bg-gradient-to-br from-gold-300/35 to-gold-500/15 text-gold-500 ring-1 ring-gold-400/25 dark:text-gold-300',
  green: 'bg-gradient-to-br from-green-300/30 to-green-500/12 text-green-700 ring-1 ring-green-500/15 dark:text-green-300',
  hint: 'bg-app-surface text-app-hint ring-1 ring-app-hint/15',
}

const GROUPS: { label: string; icon: IconName; tone: Tone; categories: string[] }[] = [
  { label: 'Davomat', icon: 'calendar', tone: 'green', categories: ['ATTENDANCE'] },
  { label: 'Testlar', icon: 'file-text', tone: 'brand', categories: ['TEST', 'TEST_RANK_BONUS'] },
  { label: 'Kitoblar', icon: 'book', tone: 'brand', categories: ['BOOK_COMPLETION', 'CAMPAIGN'] },
  { label: 'Bonuslar', icon: 'gift', tone: 'gold', categories: ['ACHIEVEMENT', 'MANUAL'] },
]

const VISIBLE = 8

function amountClass(positive: boolean): string {
  return positive ? 'text-green-600 dark:text-green-300' : 'text-app-danger'
}

/** One tappable row in the points history. Tapping it opens the full breakdown. */
function HistoryRow({ entry, onOpen }: { entry: ScoreEntry; onOpen: () => void }) {
  const meta = metaFor(entry.category)
  const positive = entry.amount > 0
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex w-full items-center gap-3 py-2.5 text-left transition active:scale-[0.99]"
    >
      <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${TONE_TILE[meta.tone]}`}>
        <Icon name={meta.icon} size={19} />
      </span>
      <span className="min-w-0 flex-1">
        <span className={`block truncate text-[15px] ${entry.is_reversed ? 'text-app-hint line-through' : ''}`}>
          {entry.source_title || meta.label}
        </span>
        <span className="block truncate text-xs text-app-hint">{meta.label} · {formatDate(entry.created_at)}</span>
      </span>
      <span className={`shrink-0 font-semibold tabular-nums ${entry.is_reversed ? 'text-app-hint' : amountClass(positive)}`}>
        {positive ? '+' : ''}
        {entry.amount}
      </span>
      <Icon name="chevron-right" size={16} className="shrink-0 text-app-hint" />
    </button>
  )
}

/** The full «why these points» breakdown for one entry — real fields only, nothing invented. */
function ScoreDetail({ entry }: { entry: ScoreEntry }) {
  const meta = metaFor(entry.category)
  const positive = entry.amount > 0
  const effective = entry.category === 'REVERSAL' ? metaFor(entry.effective_category) : null
  return (
    <div className="flex flex-col gap-4 pb-2">
      <div className="flex flex-col items-center gap-2 pt-1 text-center">
        <span className={`grid size-16 place-items-center rounded-2xl ${TONE_TILE[meta.tone]}`}>
          <Icon name={meta.icon} size={30} />
        </span>
        <p className={`font-serif text-4xl font-bold tabular-nums ${entry.is_reversed ? 'text-app-hint line-through' : amountClass(positive)}`}>
          {positive ? '+' : ''}
          {entry.amount}
          <span className="ml-1 align-middle text-base font-medium text-app-hint">ball</span>
        </p>
        <p className="font-medium">{meta.label}</p>
        {entry.is_reversed && <Badge tone="neutral"><Icon name="refresh" size={12} />Bu ball bekor qilingan</Badge>}
      </div>

      <div className="flex flex-col divide-y divide-app-hint/10 rounded-2xl bg-app-surface/60 px-3">
        {entry.source_title && <DetailRow icon="bookmark" label="Nima uchun" value={entry.source_title} />}
        {effective && <DetailRow icon="tag" label="Qaysi balldan" value={effective.label} />}
        {entry.reason && <DetailRow icon="message-square" label="Izoh" value={entry.reason} />}
        <DetailRow icon="clock" label="Sana va vaqt" value={`${formatDate(entry.created_at)} · ${formatTime(entry.created_at)}`} />
      </div>

      <p className="px-1 text-center text-xs text-app-hint">
        Ballar faqat haqiqiy faoliyatingiz — davomat, testlar, kitoblar va yutuqlar asosida beriladi.
      </p>
    </div>
  )
}

function DetailRow({ icon, label, value }: { icon: IconName; label: string; value: string }) {
  return (
    <div className="flex items-start gap-2.5 py-2.5">
      <Icon name={icon} size={16} className="mt-0.5 shrink-0 text-app-hint" />
      <div className="min-w-0 flex-1">
        <p className="text-xs text-app-hint">{label}</p>
        <p className="text-[15px]">{value}</p>
      </div>
    </div>
  )
}

export function ResultsPage() {
  useHomeBackButton()
  const statsAccess = useFeature('personal_stats')
  const { api } = useAuth()
  const scores = useAsync((signal) => api<MyScores>('/api/v1/me/scores?limit=100', { signal }))
  const ranks = useAsync((signal) => api<MyRanking>('/api/v1/me/ranking', { signal }))
  const [selected, setSelected] = useState<ScoreEntry | null>(null)
  const [expanded, setExpanded] = useState(false)

  if (scores.state.status === 'loading') return <LoadingState />
  if (scores.state.status === 'error') return <ErrorState message={scores.state.error.message} onRetry={scores.reload} />
  const data = scores.state.data
  const sum = (categories: string[]) => categories.reduce((total, key) => total + (data.breakdown[key] ?? 0), 0)
  const shown = expanded ? data.history : data.history.slice(0, VISIBLE)

  return (
    <>
      <PageTitle icon="bar-chart">Natijalarim</PageTitle>
      <Card className="relative flex flex-col items-center gap-1 overflow-hidden border-0 bg-brand-gradient py-7 text-center text-white shadow-[var(--shadow-brand)] ring-1 ring-white/10">
        <span aria-hidden className="pointer-events-none absolute -right-5 -top-6 text-gold-400/15">
          <Icon name="trophy" size={120} />
        </span>
        <p className="relative text-sm text-white/75">Jami ball</p>
        <p className="relative font-serif text-5xl font-bold tabular-nums text-gold-300">{data.total}</p>
        {data.season && (
          <p className="relative text-xs text-white/70">
            {data.season.name}: {data.season.total} ball
          </p>
        )}
      </Card>

      {statsAccess !== 'off' && (
        <button type="button" onClick={() => navigate('/stats')}>
          <Card interactive className="flex items-center justify-between gap-2 py-3 text-left">
            <span className="flex items-center gap-1.5 text-[15px] font-medium">
              <Icon name="trending-up" size={17} className="text-brand-600 dark:text-brand-300" />
              Batafsil statistika
              {statsAccess === 'premium' && (
                <span className="inline-flex items-center gap-0.5 text-app-hint">
                  · <Icon name="gem" size={13} /> Premium
                </span>
              )}
            </span>
            <Icon name="chevron-right" size={18} className="shrink-0 text-app-hint" />
          </Card>
        </button>
      )}

      <div className="grid grid-cols-2 gap-2.5">
        {GROUPS.map((group) => (
          <Card key={group.label} className="flex items-center gap-3 py-3.5">
            <span className={`grid size-11 shrink-0 place-items-center rounded-xl ${TONE_TILE[group.tone]}`}>
              <Icon name={group.icon} size={22} />
            </span>
            <span className="min-w-0">
              <span className="block font-serif text-2xl font-bold leading-none tabular-nums">{sum(group.categories)}</span>
              <span className="block truncate text-xs text-app-hint">{group.label}</span>
            </span>
          </Card>
        ))}
      </div>

      {ranks.state.status === 'success' && (
        <Card className="grid grid-cols-3 text-center">
          {(
            [
              ['Hafta', ranks.state.data.week],
              ['Oy', ranks.state.data.month],
              ['Umumiy', ranks.state.data.all],
            ] as const
          ).map(([label, row]) => (
            <div key={label}>
              <p className="text-xs text-app-hint">{label}</p>
              <p className="text-lg font-semibold">{row ? `${row.rank}-o'rin` : '—'}</p>
            </div>
          ))}
        </Card>
      )}

      <SectionTitle
        action={data.history_count > 0 ? <span className="text-sm font-normal text-app-hint">{data.history_count} ta</span> : undefined}
      >
        Ballar tarixi
      </SectionTitle>
      {data.history.length === 0 ? (
        <EmptyState icon="bar-chart" title="Hali ball yo'q">
          Tadbirlarda qatnashing, testlarni ishlang va kitoblarni o'qing — har bir ball shu yerda sababi bilan ko'rinadi.
        </EmptyState>
      ) : (
        <Card className="py-1">
          <ul className="divide-y divide-app-hint/10">
            {shown.map((entry) => (
              <li key={entry.id}>
                <HistoryRow entry={entry} onOpen={() => setSelected(entry)} />
              </li>
            ))}
          </ul>
          {data.history.length > VISIBLE && (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="mt-1 flex w-full items-center justify-center gap-1 border-t border-app-hint/10 py-2.5 text-sm font-medium text-app-link"
            >
              {expanded ? (
                <>
                  <Icon name="chevron-right" size={16} className="-rotate-90" />
                  Yig'ish
                </>
              ) : (
                <>
                  <Icon name="chevron-right" size={16} className="rotate-90" />
                  Ko'proq ko'rsatish ({data.history.length - VISIBLE} ta)
                </>
              )}
            </button>
          )}
        </Card>
      )}

      <BottomSheet open={selected !== null} onClose={() => setSelected(null)} title="Ball tafsiloti">
        {selected && <ScoreDetail entry={selected} />}
      </BottomSheet>
    </>
  )
}
