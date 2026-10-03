import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, PageHeader, Pagination, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminUser, Page } from '../types/api'
import { formatDateTime } from '../utils/format'
import { navigate } from '../utils/router'
import { MemberPicker } from './ScoresPage'

interface Overview {
  premium_members: number
  stars_total: number
  stars_this_month: number
  premium_stars: number
  donation_stars: number
  payments: number
}

interface Plan {
  id: string
  code: string
  title: string
  description: string | null
  stars: number
  days: number
  is_active: boolean
}

interface Member {
  user_id: string
  first_name: string
  last_name: string
  member_number: string
}

interface Payment {
  id: string
  kind: 'PREMIUM' | 'DONATION'
  status: 'PAID' | 'REFUNDED'
  amount: number
  plan_title: string | null
  created_at: string
  refunded_at: string | null
  member: Member
}

interface Subscription {
  id: string
  source: 'STARS' | 'MANUAL'
  starts_at: string
  ends_at: string
  note: string | null
  revoked_at: string | null
  member: Member
}

const LIMIT = 20

function PlanRow({ plan, onSaved }: { plan: Plan; onSaved: () => void }) {
  const { api } = useSession()
  const [stars, setStars] = useState(String(plan.stars))
  const [days, setDays] = useState(String(plan.days))
  const [error, setError] = useState<string | null>(null)
  const dirty = stars !== String(plan.stars) || days !== String(plan.days)

  async function save(changes: Record<string, unknown>) {
    setError(null)
    try {
      await api(`/api/v1/admin/premium/plans/${plan.id}`, { method: 'PATCH', body: changes })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik.')
    }
  }

  return (
    <tr className={plan.is_active ? '' : 'opacity-60'}>
      <td className="px-4 py-2 font-medium">
        {plan.title}
        <InlineError message={error} />
      </td>
      <td className="px-4 py-2">
        <Input type="number" min={1} value={stars} onChange={(e) => setStars(e.target.value)} className="w-24" aria-label="Narx (Stars)" />
      </td>
      <td className="px-4 py-2">
        <Input type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} className="w-20" aria-label="Kun" />
      </td>
      <td className="whitespace-nowrap px-4 py-2 text-right">
        {dirty && <Button onClick={() => void save({ stars: Number(stars), days: Number(days) })}>Saqlash</Button>}
        <Button variant="ghost" onClick={() => void save({ is_active: !plan.is_active })}>
          {plan.is_active ? 'Sotuvdan olish' : 'Sotuvga qaytarish'}
        </Button>
      </td>
    </tr>
  )
}

export function PremiumPage() {
  const { api } = useSession()
  const overview = useAsync((signal) => api<Overview>('/api/v1/admin/premium/overview', { signal }))
  const plans = useAsync((signal) => api<Plan[]>('/api/v1/admin/premium/plans', { signal }))
  const [paymentsOffset, setPaymentsOffset] = useState(0)
  const payments = useAsync(
    (signal) => api<Page<Payment>>(`/api/v1/admin/premium/payments?limit=${LIMIT}&offset=${paymentsOffset}`, { signal }),
    [paymentsOffset],
  )
  const subscriptions = useAsync((signal) => api<Page<Subscription>>('/api/v1/admin/premium/subscriptions?limit=50', { signal }))
  const [member, setMember] = useState<AdminUser | null>(null)
  const [pickerKey, setPickerKey] = useState(0)
  const [days, setDays] = useState('30')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  function reloadAll() {
    overview.reload()
    plans.reload()
    payments.reload()
    subscriptions.reload()
  }

  async function run(action: () => Promise<unknown>, done: string) {
    setError(null)
    setMessage(null)
    try {
      await action()
      setMessage(done)
      reloadAll()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    }
  }

  return (
    <>
      <PageHeader
        title="Premium va to'lovlar"
        subtitle="Premium obuna va hissalar Telegram Stars (⭐) orqali qabul qilinadi. Premium bo'limini «Imkoniyatlar» sahifasida yoqasiz."
        actions={
          <Button variant="secondary" onClick={() => navigate('/features')}>
            ⚙️ Imkoniyatlar
          </Button>
        }
      />
      <InlineError message={error} />
      {message && <p className="text-sm text-emerald-600">{message}</p>}

      {overview.state.status === 'success' && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {[
            ["💎 Premium a'zolar", overview.state.data.premium_members],
            ['⭐ Jami tushum', overview.state.data.stars_total],
            ['⭐ Shu oy', overview.state.data.stars_this_month],
            ['⭐ Premiumdan', overview.state.data.premium_stars],
            ['❤️ Hissalardan', overview.state.data.donation_stars],
          ].map(([label, value]) => (
            <Card key={label} className="p-4">
              <p className="text-sm text-app-hint">{label}</p>
              <p className="text-2xl font-semibold tabular-nums">{value}</p>
            </Card>
          ))}
        </div>
      )}

      <Card className="p-4">
        <h2 className="mb-2 font-semibold">Tariflar</h2>
        {plans.state.status === 'loading' && <LoadingState />}
        {plans.state.status === 'error' && <ErrorState message={plans.state.error.message} onRetry={plans.reload} />}
        {plans.state.status === 'success' && (
          <Table head={['Tarif', 'Narx (⭐)', 'Kun', '']}>
            {plans.state.data.map((plan) => (
              <PlanRow key={`${plan.id}-${plan.stars}-${plan.days}-${plan.is_active}`} plan={plan} onSaved={reloadAll} />
            ))}
          </Table>
        )}
        <p className="mt-2 text-xs text-app-hint">
          1 ⭐ taxminan 0,013–0,02 AQSh dollari. Yig'ilgan Stars'ni Fragment orqali naqd pulga aylantirish mumkin (yo'riqnomada).
        </p>
      </Card>

      <Card className="flex flex-col gap-3 p-4">
        <h2 className="font-semibold">Premium sovg'a qilish</h2>
        <p className="text-sm text-app-hint">Masalan, g'oliblarga yoki naqd to'lagan a'zoga. A'zoga bot orqali xabar boradi.</p>
        <MemberPicker key={pickerKey} value={member} onChange={setMember} />
        <div className="grid gap-2 sm:grid-cols-[8rem_minmax(0,1fr)_auto]">
          <Field label="Kun">
            <Input type="number" min={1} max={3660} value={days} onChange={(e) => setDays(e.target.value)} />
          </Field>
          <Field label="Izoh (ixtiyoriy)">
            <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="Oktabr g'olibi" />
          </Field>
          <div className="flex items-end">
            <Button
              disabled={!member || Number(days) < 1}
              onClick={() =>
                void run(async () => {
                  await api('/api/v1/admin/premium/grant', {
                    method: 'POST',
                    body: { user_id: member?.id, days: Number(days), note: note.trim() || null },
                  })
                  setMember(null)
                  setPickerKey((key) => key + 1)
                  setNote('')
                }, "✓ Premium berildi, a'zoga xabar yuboriladi")
              }
            >
              Berish
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="px-4 pt-4 font-semibold">Faol Premium a'zolar</h2>
        {subscriptions.state.status === 'success' && (
          <Table head={["A'zo", 'Manba', 'Muddat', '']}>
            {subscriptions.state.data.items.length === 0 && <EmptyRow colSpan={4} text="Hozircha Premium a'zolar yo'q" />}
            {subscriptions.state.data.items.map((row) => (
              <tr key={row.id}>
                <td className="px-4 py-2">
                  {row.member.last_name} {row.member.first_name}
                  <p className="font-mono text-xs text-app-hint">{row.member.member_number}</p>
                </td>
                <td className="px-4 py-2">
                  <Badge tone={row.source === 'STARS' ? 'success' : 'info'}>{row.source === 'STARS' ? '⭐ To‘lagan' : '🎁 Sovg‘a'}</Badge>
                  {row.note && <p className="text-xs text-app-hint">{row.note}</p>}
                </td>
                <td className="whitespace-nowrap px-4 py-2 text-sm">
                  {formatDateTime(row.starts_at)} → {formatDateTime(row.ends_at)}
                </td>
                <td className="px-4 py-2 text-right">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      const reason = window.prompt('Premiumni to‘xtatish sababi:')
                      if (reason && reason.trim().length >= 5)
                        void run(
                          () => api(`/api/v1/admin/premium/subscriptions/${row.id}/revoke`, { method: 'POST', body: { reason } }),
                          "✓ To'xtatildi",
                        )
                    }}
                  >
                    To'xtatish
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      <Card>
        <h2 className="px-4 pt-4 font-semibold">To'lovlar</h2>
        {payments.state.status === 'loading' && <LoadingState />}
        {payments.state.status === 'success' && (
          <>
            <Table head={["A'zo", 'Turi', 'Miqdor', 'Sana', '']}>
              {payments.state.data.items.length === 0 && <EmptyRow colSpan={5} text="Hozircha to'lovlar yo'q" />}
              {payments.state.data.items.map((payment) => (
                <tr key={payment.id} className={payment.status === 'REFUNDED' ? 'opacity-60' : ''}>
                  <td className="px-4 py-2">
                    {payment.member.last_name} {payment.member.first_name}
                  </td>
                  <td className="px-4 py-2 text-sm">
                    {payment.kind === 'PREMIUM' ? `💎 Premium ${payment.plan_title ?? ''}` : '❤️ Hissa'}
                    {payment.status === 'REFUNDED' && <Badge tone="warning">Qaytarilgan</Badge>}
                  </td>
                  <td className="px-4 py-2 tabular-nums">{payment.amount} ⭐</td>
                  <td className="whitespace-nowrap px-4 py-2 text-sm">{formatDateTime(payment.created_at)}</td>
                  <td className="px-4 py-2 text-right">
                    {payment.status === 'PAID' && (
                      <Button
                        variant="ghost"
                        onClick={() => {
                          if (window.confirm(`${payment.amount} ⭐ a'zoga qaytarilsinmi? Premium muddati ham bekor bo'ladi.`))
                            void run(() => api(`/api/v1/admin/premium/payments/${payment.id}/refund`, { method: 'POST' }), "✓ Stars qaytarildi")
                        }}
                      >
                        Qaytarish
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
            <Pagination total={payments.state.data.total} limit={LIMIT} offset={paymentsOffset} onChange={setPaymentsOffset} />
          </>
        )}
      </Card>
    </>
  )
}
