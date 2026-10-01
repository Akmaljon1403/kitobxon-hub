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
  tests: { title: string; participants: number; average_percent: number; pass_rate: number; ends_at: string }[]
  books: { title: string; author: string; status: string; deadline: string | null; readers: number; completed: number; verified: number; completion_rate: number }[]
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
      <PageHeader title="Tahlillar" subtitle="Faqat umumlashgan raqamlar. Ismlar faqat «Faol bo'lmagan a'zolar» ro'yxatida (a'zolarni ko'rish ruxsati bilan)." />
      <div className="w-48">
        <Select value={months} onChange={(e) => setMonths(Number(e.target.value))} aria-label="Davr">
          <option value={3}>So'nggi 3 oy</option>
          <option value={6}>So'nggi 6 oy</option>
          <option value={12}>So'nggi 12 oy</option>
        </Select>
      </div>
      {!data && state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {data && (
        <div className={`flex flex-col gap-4 transition-opacity ${state.status === 'loading' ? 'opacity-60' : ''}`}>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Faol a'zolar soni" value={formatNumber(data.headline.members)} />
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
            <h2 className="font-semibold">O'qish kampaniyalari</h2>
            <Table head={['Kitob', "O'quvchilar", 'Tugatgan', 'Tasdiqlangan', 'Tugatish ulushi']}>
              {data.books.length === 0 && <EmptyRow colSpan={5} text="Faol kitoblar yo'q" />}
              {data.books.map((book) => (
                <tr key={book.title}>
                  <td className="px-4 py-2">
                    <p>{book.title}</p>
                    <p className="text-xs text-app-hint">
                      {book.author}
                      {book.deadline ? ` · muddat ${formatDate(book.deadline)}` : ''}
                    </p>
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

          {can('USER_VIEW') && <Inactive />}
        </div>
      )}
    </>
  )
}
