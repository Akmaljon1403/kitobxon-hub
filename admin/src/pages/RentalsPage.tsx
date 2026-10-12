import { useState } from 'react'

import { formatNumber } from '../components/charts'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import { formatDate, formatDateTime } from '../utils/format'

type State = 'ACTIVE' | 'SOON' | 'EXPIRED' | 'NO_LICENCE' | 'ARCHIVED'

interface Plan {
  code: string
  title: string
  members: number | null
  yearly: number | null
  monthly: number | null
}

interface Org {
  id: string
  name: string
  contact_person: string | null
  phone: string | null
  telegram: string | null
  plan: string
  plan_title: string
  max_members: number | null
  price_uzs: number | null
  billing: 'YEARLY' | 'MONTHLY'
  server_url: string | null
  bot_username: string | null
  notes: string | null
  archived: boolean
  expires_on: string | null
  days_left: number | null
  state: State
  paid_total: number
  last_paid_on: string | null
}

interface Details extends Org {
  licences: { id: string; expires_on: string; max_members: number | null; issued_at: string; env: string | null }[]
  payments: { id: string; amount_uzs: number; paid_on: string; note: string | null }[]
}

interface Overview {
  public_key: string | null
  plans: Plan[]
  items: Org[]
  totals: { active: number; soon: number; expired: number; paid_this_year: number }
}

const STATES: Record<State, { text: string; tone: 'success' | 'warning' | 'danger' | 'neutral' | 'info' }> = {
  ACTIVE: { text: 'Faol', tone: 'success' },
  SOON: { text: 'Tez tugaydi', tone: 'warning' },
  EXPIRED: { text: 'Muddati tugagan', tone: 'danger' },
  NO_LICENCE: { text: 'Kalit berilmagan', tone: 'info' },
  ARCHIVED: { text: 'Arxivda', tone: 'neutral' },
}

function uzs(value: number | null): string {
  return value === null ? '—' : `${formatNumber(value)} so‘m`
}

function inAYear(): string {
  const date = new Date()
  date.setFullYear(date.getFullYear() + 1)
  return date.toISOString().slice(0, 10)
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function CopyBlock({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="flex flex-col gap-1">
      <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded-lg bg-app-surface p-3 font-mono text-xs">{text}</pre>
      <Button
        variant="secondary"
        onClick={() =>
          void navigator.clipboard?.writeText(text).then(() => {
            setCopied(true)
            window.setTimeout(() => setCopied(false), 2000)
          })
        }
      >
        {copied ? '✓ Nusxalandi' : '📋 Nusxalash'}
      </Button>
    </div>
  )
}

function KeyCard({ publicKey, onCreated }: { publicKey: string | null; onCreated: () => void }) {
  const { api } = useSession()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const [pem, setPem] = useState('')

  async function create(privatePem: string | null) {
    setBusy(true)
    setError(null)
    try {
      await api('/api/v1/admin/rentals/key', { method: 'POST', body: { private_pem: privatePem } })
      onCreated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Yaratib bo‘lmadi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <h2 className="font-semibold">🔑 Sizning litsenziya kalitingiz</h2>
      {publicKey ? (
        <>
          <p className="text-sm text-app-hint">
            Bu kalit bilan har bir tashkilotga litsenziya imzolanadi. Quyidagi «ochiq kalit» har bir ijarachi nusxasida bir xil turadi
            (LICENCE_PUBLIC_KEY). Maxfiy qismi bazada shifrlangan holda saqlanadi — SECRET_KEY o‘zgartirilmasin.
          </p>
          <CopyBlock text={`LICENCE_PUBLIC_KEY=${publicKey}`} />
        </>
      ) : (
        <>
          <p className="text-sm text-app-hint">
            Ijaraga berishni boshlash uchun bir marta kalit yarating. Uni hech kim bilmaydi va qalbaki litsenziya yasab bo‘lmaydi.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button loading={busy} onClick={() => void create(null)}>
              🔑 Kalit yaratish
            </Button>
            <Button variant="ghost" onClick={() => setImporting((value) => !value)}>
              Avval yaratilgan kalitim bor
            </Button>
          </div>
          {importing && (
            <Field label="owner-key.pem fayli matni" hint="licence_tool keygen bilan yaratilgan fayl ichidagi matnni qo‘ying">
              <Textarea rows={5} value={pem} onChange={(event) => setPem(event.target.value)} />
              <Button className="mt-2" loading={busy} disabled={!pem.trim()} onClick={() => void create(pem)}>
                Kalitni saqlash
              </Button>
            </Field>
          )}
        </>
      )}
      <InlineError message={error} />
    </Card>
  )
}

function OrgForm({ org, plans, onClose, onSaved }: { org: Org | null; plans: Plan[]; onClose: () => void; onSaved: (id: string) => void }) {
  const { api } = useSession()
  const [form, setForm] = useState({
    name: org?.name ?? '',
    contact_person: org?.contact_person ?? '',
    phone: org?.phone ?? '',
    telegram: org?.telegram ?? '',
    plan: org?.plan ?? 'MEDIUM',
    max_members: org?.max_members?.toString() ?? '1500',
    price_uzs: org?.price_uzs?.toString() ?? '6000000',
    billing: org?.billing ?? 'YEARLY',
    server_url: org?.server_url ?? '',
    bot_username: org?.bot_username ?? '',
    notes: org?.notes ?? '',
    archived: org?.archived ?? false,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (key: keyof typeof form, value: string | boolean) => setForm((current) => ({ ...current, [key]: value }))

  function choosePlan(code: string) {
    const plan = plans.find((item) => item.code === code)
    setForm((current) => ({
      ...current,
      plan: code,
      max_members: plan?.members ? String(plan.members) : code === 'CUSTOM' ? current.max_members : '',
      price_uzs:
        plan && (current.billing === 'YEARLY' ? plan.yearly : plan.monthly)
          ? String(current.billing === 'YEARLY' ? plan.yearly : plan.monthly)
          : current.price_uzs,
    }))
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const body = {
        ...form,
        max_members: form.max_members ? Number(form.max_members) : null,
        price_uzs: form.price_uzs ? Number(form.price_uzs) : null,
      }
      const result = await api<Details>(org ? `/api/v1/admin/rentals/organizations/${org.id}` : '/api/v1/admin/rentals/organizations', {
        method: org ? 'PUT' : 'POST',
        body,
      })
      onSaved(result.id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Saqlab bo‘lmadi')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={org ? `✏️ ${org.name}` : '🏢 Yangi tashkilot'}
      onClose={onClose}
      wide
      footer={
        <Button loading={busy} disabled={form.name.trim().length < 2} onClick={() => void save()}>
          Saqlash
        </Button>
      }
    >
      <Field label="Tashkilot nomi">
        <Input value={form.name} maxLength={200} placeholder="Namuna tibbiyot kolleji" onChange={(e) => set('name', e.target.value)} />
      </Field>
      <div className="grid gap-2 sm:grid-cols-3">
        <Field label="Mas’ul shaxs">
          <Input value={form.contact_person} onChange={(e) => set('contact_person', e.target.value)} />
        </Field>
        <Field label="Telefon">
          <Input value={form.phone} onChange={(e) => set('phone', e.target.value)} />
        </Field>
        <Field label="Telegram">
          <Input value={form.telegram} placeholder="@username" onChange={(e) => set('telegram', e.target.value)} />
        </Field>
      </div>
      <div className="grid gap-2 sm:grid-cols-4">
        <Field label="Tarif">
          <Select value={form.plan} onChange={(e) => choosePlan(e.target.value)}>
            {plans.map((plan) => (
              <option key={plan.code} value={plan.code}>
                {plan.title}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="A’zolar chegarasi" hint="Bo‘sh — cheklovsiz">
          <Input type="number" min={1} value={form.max_members} onChange={(e) => set('max_members', e.target.value)} />
        </Field>
        <Field label="To‘lov davri">
          <Select value={form.billing} onChange={(e) => set('billing', e.target.value)}>
            <option value="YEARLY">Yillik</option>
            <option value="MONTHLY">Oylik</option>
          </Select>
        </Field>
        <Field label="Narx (so‘m)">
          <Input type="number" min={0} value={form.price_uzs} onChange={(e) => set('price_uzs', e.target.value)} />
        </Field>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="Ularning serveri (manzil)">
          <Input value={form.server_url} placeholder="https://kollej-kitobxon.onrender.com" onChange={(e) => set('server_url', e.target.value)} />
        </Field>
        <Field label="Ularning boti">
          <Input value={form.bot_username} placeholder="@kollej_kitobxon_bot" onChange={(e) => set('bot_username', e.target.value)} />
        </Field>
      </div>
      <Field label="Izoh">
        <Textarea rows={3} value={form.notes} onChange={(e) => set('notes', e.target.value)} />
      </Field>
      {org && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={form.archived} onChange={(e) => set('archived', e.target.checked)} />
          Arxivga olish (ijara tugagan)
        </label>
      )}
      <InlineError message={error} />
    </Modal>
  )
}

function OrgDetails({ id, plans, onClose, onChanged }: { id: string; plans: Plan[]; onClose: () => void; onChanged: () => void }) {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<Details>(`/api/v1/admin/rentals/organizations/${id}`, { signal }), [id])
  const [until, setUntil] = useState(inAYear())
  const [members, setMembers] = useState<string | null>(null)
  const [issued, setIssued] = useState<string | null>(null)
  const [amount, setAmount] = useState('')
  const [paidOn, setPaidOn] = useState(today())
  const [note, setNote] = useState('')
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(name: string, action: () => Promise<void>) {
    setBusy(name)
    setError(null)
    try {
      await action()
      reload()
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bajarib bo‘lmadi')
    } finally {
      setBusy(null)
    }
  }

  if (state.status !== 'success') {
    return (
      <Modal title="🏢 Tashkilot" onClose={onClose} wide>
        {state.status === 'loading' ? <LoadingState /> : <ErrorState message={state.status === 'error' ? state.error.message : ''} onRetry={reload} />}
      </Modal>
    )
  }
  const org = state.data
  const memberLimit = members ?? (org.max_members?.toString() ?? '')

  return (
    <Modal title={`🏢 ${org.name}`} onClose={onClose} wide footer={<Button variant="secondary" onClick={() => setEditing(true)}>✏️ Tahrirlash</Button>}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge tone={STATES[org.state].tone}>{STATES[org.state].text}</Badge>
        <span>{org.plan_title}</span>
        <span className="text-app-hint">
          · {org.max_members ? `${formatNumber(org.max_members)} a’zogacha` : 'cheklovsiz'} · {uzs(org.price_uzs)} ({org.billing === 'YEARLY' ? 'yillik' : 'oylik'})
        </span>
      </div>
      <p className="text-sm text-app-hint">
        {[org.contact_person, org.phone, org.telegram, org.bot_username, org.server_url].filter(Boolean).join(' · ') || 'Aloqa ma’lumotlari kiritilmagan'}
      </p>

      <section className="flex flex-col gap-2 rounded-lg border border-app-border p-3">
        <h3 className="font-semibold">🔐 Litsenziya kaliti berish</h3>
        <p className="text-sm text-app-hint">
          Kalit ularning nusxasida «{org.name}» nomi, tugash sanasi va a’zolar chegarasi bilan ishlaydi. Muddat tugagach 7 kun imtiyoz, keyin a’zolar
          uchun xizmat to‘xtaydi (adminlar ishlayveradi). Uzaytirish — yangi kalit berish.
        </p>
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
          <Field label="Qachongacha">
            <Input type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
          </Field>
          <Field label="A’zolar chegarasi" hint="Bo‘sh — cheklovsiz">
            <Input type="number" min={1} value={memberLimit} onChange={(e) => setMembers(e.target.value)} />
          </Field>
          <div className="flex items-end">
            <Button
              loading={busy === 'issue'}
              onClick={() =>
                void run('issue', async () => {
                  const result = await api<{ env: string }>(`/api/v1/admin/rentals/organizations/${org.id}/licences`, {
                    method: 'POST',
                    body: { expires_on: until, max_members: memberLimit ? Number(memberLimit) : null },
                  })
                  setIssued(result.env)
                })
              }
            >
              🔐 Kalit berish
            </Button>
          </div>
        </div>
        {issued && (
          <div className="flex flex-col gap-1 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
            <p className="font-semibold">✅ Kalit tayyor. Ularning serverida (Render → xizmat → Environment) shu 3 qatorni qo‘ying va «Save»:</p>
            <CopyBlock text={issued} />
          </div>
        )}
        {org.licences.length > 0 && (
          <Table head={['Berilgan', 'Qachongacha', 'A’zolar', '']}>
            {org.licences.map((row) => (
              <tr key={row.id}>
                <td className="px-4 py-2">{formatDateTime(row.issued_at)}</td>
                <td className="px-4 py-2">{formatDate(row.expires_on)}</td>
                <td className="px-4 py-2 tabular-nums">{row.max_members ? formatNumber(row.max_members) : 'cheklovsiz'}</td>
                <td className="px-4 py-2 text-right">
                  {row.env && (
                    <Button variant="ghost" onClick={() => setIssued(row.env)}>
                      Ko‘rsatish
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </section>

      <section className="flex flex-col gap-2 rounded-lg border border-app-border p-3">
        <h3 className="font-semibold">💵 To‘lovlar · jami {uzs(org.paid_total)}</h3>
        <div className="grid gap-2 sm:grid-cols-[1fr_1fr_2fr_auto]">
          <Field label="Summa (so‘m)">
            <Input type="number" min={1} value={amount} onChange={(e) => setAmount(e.target.value)} />
          </Field>
          <Field label="Sana">
            <Input type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} />
          </Field>
          <Field label="Izoh">
            <Input value={note} maxLength={255} placeholder="2026–2027 o‘quv yili uchun" onChange={(e) => setNote(e.target.value)} />
          </Field>
          <div className="flex items-end">
            <Button
              loading={busy === 'pay'}
              disabled={!amount}
              onClick={() =>
                void run('pay', async () => {
                  await api(`/api/v1/admin/rentals/organizations/${org.id}/payments`, {
                    method: 'POST',
                    body: { amount_uzs: Number(amount), paid_on: paidOn, note: note.trim() || null },
                  })
                  setAmount('')
                  setNote('')
                })
              }
            >
              Qo‘shish
            </Button>
          </div>
        </div>
        <Table head={['Sana', 'Summa', 'Izoh', '']}>
          {org.payments.length === 0 && <EmptyRow colSpan={4} text="Hali to‘lov yozilmagan" />}
          {org.payments.map((row) => (
            <tr key={row.id}>
              <td className="px-4 py-2">{formatDate(row.paid_on)}</td>
              <td className="px-4 py-2 tabular-nums">{uzs(row.amount_uzs)}</td>
              <td className="px-4 py-2">{row.note ?? '—'}</td>
              <td className="px-4 py-2 text-right">
                <Button
                  variant="ghost"
                  onClick={() => {
                    if (window.confirm('To‘lov yozuvi o‘chirilsinmi?'))
                      void run('del', () => api(`/api/v1/admin/rentals/payments/${row.id}`, { method: 'DELETE' }).then(() => undefined))
                  }}
                >
                  🗑
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      </section>
      {org.notes && <p className="whitespace-pre-line text-sm">📝 {org.notes}</p>}
      <InlineError message={error} />
      {editing && (
        <OrgForm
          org={org}
          plans={plans}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false)
            reload()
            onChanged()
          }}
        />
      )}
    </Modal>
  )
}

/** «🏢 Ijara»: copies of Kitobxon Hub rented to other organisations — keys, licences, payments. */
export function RentalsPage() {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<Overview>('/api/v1/admin/rentals', { signal }), [])
  const [creating, setCreating] = useState(false)
  const [open, setOpen] = useState<string | null>(null)

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="🏢 Ijara (tashkilotlar)"
        subtitle="Kitobxon Hub’ni boshqa institut, kollej va maktablarga ijaraga berish. Har bir tashkilot o‘z serveri, bazasi va boti bilan alohida ishlaydi — ma’lumotlar hech qachon aralashmaydi. Bu sahifa faqat sizda: kalitlar, muddatlar va to‘lovlar."
        actions={
          <Button disabled={state.status !== 'success' || !state.data.public_key} onClick={() => setCreating(true)}>
            + Yangi tashkilot
          </Button>
        }
      />
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              ['Faol tashkilotlar', formatNumber(state.data.totals.active)],
              ['30 kunda tugaydi', formatNumber(state.data.totals.soon)],
              ['Muddati tugagan', formatNumber(state.data.totals.expired)],
              ['Bu yil tushum', uzs(state.data.totals.paid_this_year)],
            ].map(([label, value]) => (
              <Card key={label} className="p-4">
                <p className="text-sm text-app-hint">{label}</p>
                <p className="text-xl font-semibold tabular-nums">{value}</p>
              </Card>
            ))}
          </div>
          <KeyCard publicKey={state.data.public_key} onCreated={reload} />
          <Card>
            <Table head={['Tashkilot', 'Tarif', 'Holat', 'Qachongacha', 'To‘langan', '']}>
              {state.data.items.length === 0 && <EmptyRow colSpan={6} text="Hali tashkilot qo‘shilmagan" />}
              {state.data.items.map((org) => (
                <tr key={org.id} className="cursor-pointer hover:bg-app-surface" onClick={() => setOpen(org.id)}>
                  <td className="px-4 py-2">
                    <p className="font-medium">{org.name}</p>
                    <p className="text-xs text-app-hint">{[org.contact_person, org.phone].filter(Boolean).join(' · ')}</p>
                  </td>
                  <td className="px-4 py-2 text-sm">
                    {org.plan_title}
                    <p className="text-xs text-app-hint">{org.max_members ? `${formatNumber(org.max_members)} a’zogacha` : 'cheklovsiz'}</p>
                  </td>
                  <td className="px-4 py-2">
                    <Badge tone={STATES[org.state].tone}>{STATES[org.state].text}</Badge>
                  </td>
                  <td className="px-4 py-2 text-sm">
                    {org.expires_on ? formatDate(org.expires_on) : '—'}
                    {org.days_left !== null && <p className="text-xs text-app-hint">{org.days_left >= 0 ? `${org.days_left} kun qoldi` : `${-org.days_left} kun o‘tdi`}</p>}
                  </td>
                  <td className="px-4 py-2 text-sm tabular-nums">{uzs(org.paid_total)}</td>
                  <td className="px-4 py-2 text-right">
                    <Button variant="ghost">Ochish</Button>
                  </td>
                </tr>
              ))}
            </Table>
          </Card>
          <Card className="flex flex-col gap-2 p-4 text-sm">
            <h2 className="font-semibold">📋 Yangi tashkilotni ulash — qadamlar</h2>
            <ol className="list-decimal space-y-1 pl-5">
              <li>Tashkilot o‘z Telegram botini @BotFather’da yaratadi va tokenni sizga xavfsiz yo‘l bilan beradi (chatga yozilmasin).</li>
              <li>Render’da yangi xizmat (shu loyihaning Blueprint’i) — alohida server va alohida baza bilan ochiladi.</li>
              <li>Environment’ga ularning BOT_TOKEN, SUPER_ADMIN_TELEGRAM_IDS (ularning bosh admini) va shu sahifada berilgan 3 qator LICENCE_… yoziladi.</li>
              <li>Deploy tugagach, ularning bosh admini botda /start → «🛠 Boshqaruv». Muddat yaqinlashganda «Xayrli tong» xabarida eslatma chiqadi.</li>
            </ol>
          </Card>
          {creating && (
            <OrgForm
              org={null}
              plans={state.data.plans}
              onClose={() => setCreating(false)}
              onSaved={(id) => {
                setCreating(false)
                reload()
                setOpen(id)
              }}
            />
          )}
          {open && <OrgDetails id={open} plans={state.data.plans} onClose={() => setOpen(null)} onChanged={reload} />}
        </>
      )}
    </div>
  )
}
