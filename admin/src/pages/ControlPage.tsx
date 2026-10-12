import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, PageHeader } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useSession } from '../store/session'
import { formatDateTime } from '../utils/format'
import { navigate } from '../utils/router'

interface Queue {
  code: string
  title: string
  count: number
  oldest_minutes: number | null
  route: string
}

interface Control {
  queues: Queue[]
  waiting_total: number
  failed_posts_week: number
  notifications: { pending: number; sent_24h: number; failed_24h: number; skipped_24h: number }
  recent: { at: string; who: string; action: string; what: string; entity: string }[]
  answers_week: { who: string; count: number }[]
}

function waited(minutes: number | null): string {
  if (minutes === null) return ''
  if (minutes < 60) return `${minutes} daqiqa`
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)} soat`
  return `${Math.floor(minutes / 1440)} kun`
}

/** «🛰 Nazorat markazi»: the super admin sees every process at once and steps in anywhere. */
export function ControlPage() {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<Control>('/api/v1/admin/control', { signal }))

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const data = state.data
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="🛰 Nazorat markazi"
        subtitle="Hamma jarayon bir joyda: nima kutmoqda va qancha vaqtdan beri, kim nima qildi. Istalgan qatorni bosing — o‘sha bo‘limda o‘zingiz hal qilasiz; qaroringiz boshqa adminlarning botdagi nusxalarida ham ko‘rinadi."
        actions={
          <Button variant="secondary" onClick={reload}>
            🔄 Yangilash
          </Button>
        }
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.queues.map((queue) => (
          <button key={queue.code} type="button" className="text-left" onClick={() => navigate(`/${queue.route}`)}>
            <Card className={`flex h-full flex-col gap-1 p-4 ${queue.count ? 'ring-1 ring-amber-400/60' : ''}`}>
              <p className="text-sm text-app-hint">{queue.title}</p>
              <p className="text-3xl font-semibold tabular-nums">{queue.count}</p>
              {queue.count > 0 && queue.oldest_minutes !== null && (
                <p className="text-xs text-amber-700 dark:text-amber-400">eng eskisi: {waited(queue.oldest_minutes)} kutmoqda</p>
              )}
              {queue.count === 0 && <p className="text-xs text-emerald-600">✓ hammasi hal qilingan</p>}
            </Card>
          </button>
        ))}
        <Card className="flex flex-col gap-1 p-4">
          <p className="text-sm text-app-hint">📬 Bot xabarlari navbati</p>
          <p className="text-3xl font-semibold tabular-nums">{data.notifications.pending}</p>
          <p className="text-xs text-app-hint">
            24 soatda: {data.notifications.sent_24h} yuborildi · {data.notifications.failed_24h} xato · {data.notifications.skipped_24h} o‘tkazildi
          </p>
          {data.failed_posts_week > 0 && <Badge tone="danger">Kanalga chiqmagan postlar (7 kun): {data.failed_posts_week}</Badge>}
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card className="p-0">
          <h2 className="border-b border-app-border px-4 py-3 font-semibold">🧾 So‘nggi harakatlar</h2>
          <ul className="divide-y divide-app-border text-sm">
            {data.recent.length === 0 && <li className="px-4 py-6 text-center text-app-hint">Hali harakat yo‘q</li>}
            {data.recent.map((item, index) => (
              <li key={index} className="flex flex-wrap items-baseline justify-between gap-2 px-4 py-2">
                <span>
                  <b>{item.who}</b> {item.what}
                </span>
                <span className="text-xs text-app-hint">{formatDateTime(item.at)}</span>
              </li>
            ))}
          </ul>
          <div className="border-t border-app-border px-4 py-2 text-right">
            <Button variant="ghost" onClick={() => navigate('/audit')}>
              Hammasi — audit jurnalida →
            </Button>
          </div>
        </Card>
        <Card className="p-0">
          <h2 className="border-b border-app-border px-4 py-3 font-semibold">📨 Shu hafta kim javob berdi</h2>
          <ul className="divide-y divide-app-border text-sm">
            {data.answers_week.length === 0 && <li className="px-4 py-6 text-center text-app-hint">Bu hafta javoblar yo‘q</li>}
            {data.answers_week.map((row) => (
              <li key={row.who} className="flex justify-between px-4 py-2">
                <span>{row.who}</span>
                <span className="tabular-nums">{row.count}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}
