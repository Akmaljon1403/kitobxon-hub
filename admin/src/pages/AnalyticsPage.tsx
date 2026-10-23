import { useEffect, useState } from 'react'

import { BarList, ChartCard, ColumnChart, Meter, StatTile, formatNumber, monthLabel } from '../components/charts'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Card, EmptyRow, PageHeader, Select, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useSession } from '../store/session'
import { formatDate } from '../utils/format'

interface Analytics {
  months: string[]
  headline: {
    members: number
    active_30_days: number
    inactive_30_days: number
    test_participants: number
    average_test_percent: number | null
  }
  by_month: Record<'new_members' | 'active_members' | 'attendance' | 'events' | 'books_completed', number[]>
  points_distribution: { bucket: string; members: number }[]
  faculties: { name: string; members: number; active_30_days: number; total_points: number; average_points: number; attendance: number }[]
  groups: { group: string; faculty: string | null; members: number; average_points: number }[]
  groups_all: { group: string; faculty: string | null; course: number | null; members: number; active_30_days: number; attendance: number; total_points: number; average_points: number }[]
  tests: { title: string; participants: number; average_percent: number; pass_rate: number; ends_at: string }[]
  books: { title: string; author: string; status: string; deadline: string | null; readers: number; completed: number; verified: number; completion_rate: number }[]
  top_rated: { title: string; author: string; average: number; ratings: number }[]
}

interface Reflection {
  id: string
  user_id: string
  first_name: string
  last_name: string
  book_title: string
  book_author: string | null
  rating: number | null
  main_idea: string
  favorite_moment: string
  apply_in_life: string
  created_at: string
}

interface InactiveMember {
  user_id: string
  first_name: string
  last_name: string
  faculty: string | null
  course: number | null
  group_name: string | null
  registered_at: string | null
  last_activity_at: string | null
}

const MONTHLY: { key: keyof Analytics['by_month']; title: string; subtitle: string }[] = [
  { key: 'active_members', title: "Faol a'zolar", subtitle: "Oy davomida davomat, test yoki kitob uchun ball olgan a'zolar" },
  { key: 'attendance', title: 'Tasdiqlangan davomat', subtitle: 'QR/kod yoki admin orqali qayd etilgan qatnashuvlar' },
  { key: 'new_members', title: "Yangi a'zolar", subtitle: "Botda ro'yxatdan o'tganlar" },
  { key: 'books_completed', title: "O'qib tugatilgan kitoblar", subtitle: "A'zolar belgilagan tugatishlar" },
]

interface Engagement {
  months: { month: string; active: number; new: number; returning: number; churned: number; retention: number | null }[]
  last_30_days: {
    members: number
    diary_members: number
    diary_share: number
    pages: number
    books_finished: number
    quotes: number
    reflections: number
    missions_taken: number
    missions_completed: number
    missions_rate: number | null
  }
}

/** «Faollik va qaytish»: who came back, who stopped, and how the reading tools are used. */
function EngagementSection() {
  const { api } = useSession()
  const { state } = useAsync((signal) => api<Engagement>('/api/v1/admin/analytics/engagement', { signal }))
  if (state.status !== 'success') return null
  const { months, last_30_days: last } = state.data
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h2 className="font-semibold">🔁 Faollik va qaytish</h2>
        <p className="text-sm text-app-hint">
          Faol — oy davomida ball olgan, kundalikka yozgan yoki tadbirga kelgan a’zo. Qaytgan — o‘tgan oy ham faol bo‘lgan; to‘xtagan — o‘tgan
          oy faol edi, bu oy yo‘q.
        </p>
      </div>
      <Table head={['Oy', 'Faol', 'Yangi', 'Qaytgan', 'To‘xtagan', 'Saqlanish']}>
        {months.map((row) => (
          <tr key={row.month}>
            <td className="px-4 py-2">{monthLabel(row.month)}</td>
            <td className="px-4 py-2 tabular-nums">{formatNumber(row.active)}</td>
            <td className="px-4 py-2 tabular-nums">{formatNumber(row.new)}</td>
            <td className="px-4 py-2 tabular-nums">{formatNumber(row.returning)}</td>
            <td className="px-4 py-2 tabular-nums">{formatNumber(row.churned)}</td>
            <td className="px-4 py-2">{row.retention === null ? '—' : <Meter value={row.retention} label={`${row.retention}%`} />}</td>
          </tr>
        ))}
      </Table>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Kundalik yuritayotganlar (30 kun)" value={`${last.diary_members} (${last.diary_share}%)`} note={`${formatNumber(last.pages)} bet yozildi`} />
        <StatTile label="O‘qib tugatilgan kitoblar (javon)" value={formatNumber(last.books_finished)} note={`«3 savol» javoblari: ${last.reflections}`} />
        <StatTile label="Saqlangan iqtiboslar" value={formatNumber(last.quotes)} />
        <StatTile
          label="Missiyalar: olindi / bajarildi"
          value={`${last.missions_taken} / ${last.missions_completed}`}
          note={last.missions_rate === null ? undefined : `bajarilish ${last.missions_rate}%`}
        />
      </div>
    </Card>
  )
}

function Inactive() {
  const { api } = useSession()
  const [days, setDays] = useState(30)
  const { state } = useAsync((signal) => api<InactiveMember[]>(`/api/v1/admin/analytics/inactive?days=${days}`, { signal }), [days])
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">Faol bo'lmagan a'zolar</h2>
          <p className="text-xs text-app-hint">Davomat, test yoki kitob bo'yicha faolligi bo'lmaganlar — ularni tadbirga taklif qilish mumkin</p>
        </div>
        <div className="w-44">
          <Select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Davr">
            <option value={30}>30 kundan beri</option>
            <option value={60}>60 kundan beri</option>
            <option value={90}>90 kundan beri</option>
          </Select>
        </div>
      </div>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'success' && (
        <Table head={["A'zo", 'Fakultet', 'Kurs / guruh', "So'nggi faollik"]}>
          {state.data.length === 0 && <EmptyRow colSpan={4} text="Hamma faol 🎉" />}
          {state.data.map((member) => (
            <tr key={member.user_id}>
              <td className="px-4 py-2">
                {member.last_name} {member.first_name}
              </td>
              <td className="px-4 py-2 text-sm">{member.faculty ?? '—'}</td>
              <td className="px-4 py-2 text-sm">
                {member.course ? `${member.course}-kurs` : '—'} {member.group_name ? `· ${member.group_name}` : ''}
              </td>
              <td className="px-4 py-2 text-sm">{member.last_activity_at ? formatDate(member.last_activity_at) : 'hali yo\'q'}</td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  )
}

/** «Kitob mulohazalari»: the three answers members write in their reading diary after a book. */
function Reflections() {
  const { api } = useSession()
  const [page, setPage] = useState(0)
  const limit = 10
  const { state } = useAsync(
    (signal) => api<{ total: number; items: Reflection[] }>(`/api/v1/admin/analytics/reflections?limit=${limit}&offset=${page * limit}`, { signal }),
    [page],
  )
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h2 className="font-semibold">📖 Kitob mulohazalari (3 savol)</h2>
        <p className="text-xs text-app-hint">A'zolar kitobni o'qib tugatgach kundaligida yozgan javoblari — eng yangisi birinchi</p>
      </div>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} />}
      {state.status === 'success' && state.data.items.length === 0 && (
        <p className="py-6 text-center text-sm text-app-hint">Hali mulohaza yozilmagan.</p>
      )}
      {state.status === 'success' &&
        state.data.items.map((item) => (
          <article key={item.id} className="rounded-xl border border-app-border p-3.5">
            <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <p className="font-medium">
                {item.last_name} {item.first_name}
                <span className="ml-2 text-sm font-normal text-app-hint">
                  📚 {item.book_title}
                  {item.book_author ? ` — ${item.book_author}` : ''}
                </span>
              </p>
              <span className="text-xs text-app-hint">
                {item.rating ? `${'⭐'.repeat(item.rating)} · ` : ''}
                {formatDate(item.created_at)}
              </span>
            </header>
            <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs font-semibold text-app-hint">Asosiy g'oya</dt>
                <dd className="mt-0.5 whitespace-pre-line">{item.main_idea}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-app-hint">Yoqqan lahza</dt>
                <dd className="mt-0.5 whitespace-pre-line">{item.favorite_moment}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-app-hint">Hayotda qo'llash</dt>
                <dd className="mt-0.5 whitespace-pre-line">{item.apply_in_life}</dd>
              </div>
            </dl>
          </article>
        ))}
      {state.status === 'success' && state.data.total > limit && (
        <div className="flex items-center justify-between gap-2 text-sm">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="rounded-lg border border-app-border px-3 py-1.5 disabled:opacity-40"
          >
            ← Oldingi
          </button>
          <span className="text-app-hint tabular-nums">
            {page * limit + 1}–{Math.min((page + 1) * limit, state.data.total)} / {state.data.total}
          </span>
          <button
            type="button"
            disabled={(page + 1) * limit >= state.data.total}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-app-border px-3 py-1.5 disabled:opacity-40"
          >
            Keyingi →
          </button>
        </div>
      )}
    </Card>
  )
}

/** «Guruhlar kesimida»: every group in the usual order — faculty, then the group number (5424, 5524, …). */
function GroupsTable({ rows }: { rows: Analytics['groups_all'] }) {
  let faculty: string | null | undefined
  return (
    <Card className="flex flex-col gap-2 p-4">
      <div>
        <h2 className="font-semibold">Guruhlar kesimida</h2>
        <p className="text-sm text-app-hint">Fakultet, so‘ng guruh raqami tartibida: 5424, 5524, …</p>
      </div>
      <Table head={['Guruh', 'Kurs', "A'zolar", 'Faol (30 kun)', 'Davomat', 'Jami ball', "O'rtacha ball"]}>
        {rows.length === 0 && <EmptyRow colSpan={7} text="Guruhlar hali yo'q" />}
        {rows.flatMap((row) => {
          const header =
            row.faculty !== faculty ? (
              <tr key={`f-${row.faculty ?? '—'}`}>
                <td colSpan={7} className="bg-app-surface px-4 py-1.5 text-xs font-semibold uppercase tracking-wide text-app-hint">
                  {row.faculty ?? 'Fakultetsiz'}
                </td>
              </tr>
            ) : null
          faculty = row.faculty
          return [
            header,
            <tr key={`${row.faculty ?? '—'}-${row.group}`}>
              <td className="px-4 py-2 font-medium">{row.group}</td>
              <td className="px-4 py-2 tabular-nums">{row.course ?? '—'}</td>
              <td className="px-4 py-2 tabular-nums">{formatNumber(row.members)}</td>
              <td className="px-4 py-2 tabular-nums">{formatNumber(row.active_30_days)}</td>
              <td className="px-4 py-2 tabular-nums">{formatNumber(row.attendance)}</td>
              <td className="px-4 py-2 tabular-nums">{formatNumber(row.total_points)}</td>
              <td className="px-4 py-2 tabular-nums">{row.average_points}</td>
            </tr>,
          ]
        })}
      </Table>
    </Card>
  )
}

export function AnalyticsPage() {
  const { api, can } = useSession()
  const [months, setMonths] = useState(6)
  const { state, reload } = useAsync((signal) => api<Analytics>(`/api/v1/admin/analytics?months=${months}`, { signal }), [months])
  // Keep the previous numbers on screen while a new range loads (no layout jump).
  const [last, setLast] = useState<Analytics | null>(null)
  useEffect(() => {
    if (state.status === 'success') setLast(state.data)
  }, [state])
  const data = state.status === 'success' ? state.data : last

  return (
    <>
      <PageHeader title="Tahlillar" subtitle="Asosan umumlashgan raqamlar. Ismlar faqat «Kitob mulohazalari» va «Faol bo'lmagan a'zolar» bo'limlarida (a'zolarni ko'rish ruxsati bilan)." />
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-app-hint">Davr:</span>
        {[3, 6, 12, 24].map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setMonths(option)}
            className={`rounded-lg border px-3 py-1.5 text-sm ${months === option ? 'border-app-button bg-app-button/10 font-medium' : 'border-app-border'}`}
          >
            {option} oy
          </button>
        ))}
        <label className="flex items-center gap-1.5 text-sm text-app-hint">
          Boshqa:
          <input
            type="number"
            min={3}
            max={24}
            value={months}
            onChange={(e) => {
              const value = Number(e.target.value)
              if (value >= 3 && value <= 24) setMonths(value)
            }}
            aria-label="Oylar soni (3–24)"
            className="w-16 rounded-lg border border-app-border bg-transparent px-2 py-1 tabular-nums"
          />
          oy
        </label>
      </div>
      {!data && state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {data && (
        <div className={`flex flex-col gap-4 transition-opacity ${state.status === 'loading' ? 'opacity-60' : ''}`}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Jami a'zolar" value={formatNumber(data.headline.members)} note="Botda faol ro'yxatda turganlar" />
            <StatTile
              label="So'nggi 30 kunda faol"
              value={formatNumber(data.headline.active_30_days)}
              note={data.headline.members ? `${Math.round((data.headline.active_30_days / data.headline.members) * 100)}% a'zolar` : undefined}
            />
            <StatTile label="30 kundan beri faolsiz" value={formatNumber(data.headline.inactive_30_days)} note="Yangi qo'shilganlar hisobga olinmaydi" />
            <StatTile
              label="Testlarda o'rtacha natija"
              value={data.headline.average_test_percent != null ? `${data.headline.average_test_percent}%` : '—'}
              note={`${data.headline.test_participants} ishtirokchi`}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {MONTHLY.map((chart) => (
              <ChartCard
                key={chart.key}
                title={chart.title}
                subtitle={chart.subtitle}
                table={{ head: ['Oy', 'Soni'], rows: data.months.map((month, i) => [monthLabel(month, true), data.by_month[chart.key][i]]) }}
              >
                <ColumnChart
                  labels={data.months.map((month) => monthLabel(month))}
                  tooltipLabels={data.months.map((month) => monthLabel(month, true))}
                  values={data.by_month[chart.key]}
                />
              </ChartCard>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard
              title="Fakultetlar: o'rtacha ball"
              subtitle="Bir a'zoga to'g'ri keladigan ball — katta va kichik fakultetlar adolatli solishtiriladi"
              table={{
                head: ['Fakultet', "A'zolar", 'Faol (30 kun)', 'Davomat', "O'rtacha ball"],
                rows: data.faculties.map((row) => [row.name, row.members, row.active_30_days, row.attendance, row.average_points]),
              }}
            >
              <BarList rows={data.faculties.map((row) => ({ label: row.name, sublabel: `${row.members} a'zo`, value: row.average_points }))} />
            </ChartCard>
            <ChartCard
              title="Eng faol guruhlar"
              subtitle="O'rtacha ball bo'yicha top-10 (kamida 3 a'zoli guruhlar)"
              table={{ head: ['Guruh', "A'zolar", "O'rtacha ball"], rows: data.groups.map((row) => [`${row.group} (${row.faculty ?? '—'})`, row.members, row.average_points]) }}
            >
              {data.groups.length ? (
                <BarList rows={data.groups.map((row) => ({ label: row.group, sublabel: row.faculty ?? undefined, value: row.average_points }))} />
              ) : (
                <p className="text-sm text-app-hint">Hali yetarli ma'lumot yo'q.</p>
              )}
            </ChartCard>
          </div>

          <GroupsTable rows={data.groups_all} />

          <ChartCard
            title="Ballar taqsimoti"
            subtitle="Nechta a'zo qancha ball to'plagan (umumiy hisob)"
            table={{ head: ['Ball', "A'zolar"], rows: data.points_distribution.map((row) => [row.bucket, row.members]) }}
          >
            <ColumnChart labels={data.points_distribution.map((row) => row.bucket)} tooltipLabels={data.points_distribution.map((row) => `${row.bucket} ball`)} values={data.points_distribution.map((row) => row.members)} unit=" a'zo" labelLast={false} />
          </ChartCard>

          <Card className="flex flex-col gap-2 p-4">
            <h2 className="font-semibold">Testlar</h2>
            <Table head={['Test', 'Ishtirokchi', "O'rtacha natija", "O'tganlar"]}>
              {data.tests.length === 0 && <EmptyRow colSpan={4} text="Hali natijali test yo'q" />}
              {data.tests.map((test) => (
                <tr key={test.title + test.ends_at}>
                  <td className="px-4 py-2">{test.title}</td>
                  <td className="px-4 py-2 tabular-nums">{test.participants}</td>
                  <td className="px-4 py-2">
                    <Meter value={test.average_percent} label="O'rtacha natija" />
                  </td>
                  <td className="px-4 py-2">
                    <Meter value={test.pass_rate} label="O'tganlar ulushi" />
                  </td>
                </tr>
              ))}
            </Table>
          </Card>

          <Card className="flex flex-col gap-2 p-4">
            <h2 className="font-semibold">Kitoblar</h2>
            <Table head={['Kitob', "O'quvchilar", 'Tugatgan', 'Tasdiqlangan', 'Tugatish ulushi']}>
              {data.books.length === 0 && <EmptyRow colSpan={5} text="Faol kitoblar yo'q" />}
              {data.books.map((book) => (
                <tr key={book.title}>
                  <td className="px-4 py-2">
                    <p>{book.title}</p>
                    <p className="text-xs text-app-hint">{book.author}</p>
                  </td>
                  <td className="px-4 py-2 tabular-nums">{book.readers}</td>
                  <td className="px-4 py-2 tabular-nums">{book.completed}</td>
                  <td className="px-4 py-2 tabular-nums">{book.verified}</td>
                  <td className="px-4 py-2">
                    <Meter value={book.completion_rate} label="Tugatganlar ulushi" />
                  </td>
                </tr>
              ))}
            </Table>
          </Card>

          {data.top_rated.length > 0 && (
            <ChartCard
              title="⭐ Eng sevilgan kitoblar"
              subtitle="A'zolar kundaligida bergan baho bo'yicha (1–5 yulduz), o'rtacha baho tartibida"
              table={{
                head: ['Kitob', 'Baho (5 dan)', 'Baholaganlar'],
                rows: data.top_rated.map((book) => [`${book.title}${book.author ? ` — ${book.author}` : ''}`, book.average, book.ratings]),
              }}
            >
              <BarList
                rows={data.top_rated.map((book) => ({
                  label: book.title,
                  sublabel: `${'⭐'.repeat(Math.round(book.average))} · ${book.ratings} baho`,
                  value: book.average,
                }))}
              />
            </ChartCard>
          )}

          <EngagementSection />

          {can('USER_VIEW') && <Reflections />}

          {can('USER_VIEW') && <Inactive />}
        </div>
      )}
    </>
  )
}
