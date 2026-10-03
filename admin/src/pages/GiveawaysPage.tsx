import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminReward, Giveaway, GiveawayAudience, GiveawayPreview, GiveawayPrize, GiveawayRule } from '../types/api'
import { formatDateTime, fromLocalInput, toLocalInput } from '../utils/format'

const RULES: Record<GiveawayRule, { title: string; hint: string; count: string }> = {
  RANDOM: {
    title: "🎲 Tasodifiy g'oliblar",
    hint: "Tanlangan a'zolar orasidan tasodifiy. Adminlar qatnashmaydi. Premium a'zolarga ikki baravar imkoniyat berish mumkin.",
    count: "G'oliblar soni",
  },
  TEST_TOP: {
    title: "📝 Testlarda eng ko'p ball",
    hint: "Davr ichida testlardan eng ko'p ball to'plaganlar (o'rin bonuslari bilan). Masalan: «Oyning eng yaxshi test ishlovchisi» — 1 g'olib.",
    count: "G'oliblar soni",
  },
  EVENT_PLACES: {
    title: "📅 Har bir tadbir testining o'rinlari",
    hint: "Davrdagi har bir tadbir testining 1-, 2-, 3-o'rinlari — har bir tadbir alohida (4 tadbir × 3 o'rin = 12 g'olib). Faqat davomatdan o'tganlar hisoblanadi.",
    count: "Har tadbirdan nechta o'rin",
  },
  RANKING_TOP: {
    title: '🏆 Reyting peshqadamlari',
    hint: "Davr bo'yicha klub reytingidagi eng yuqori o'rinlar.",
    count: "G'oliblar soni",
  },
  NEW_MEMBERS: {
    title: "🆕 Botga qo'shilgan birinchi a'zolar",
    hint: "Davr ichida botga qo'shilgan birinchi N kishi — sovg'a ro'yxatdan o'tishi bilan darhol beriladi (masalan: 1–15-noyabr, birinchi 50 kishiga Premium −50%). Adminlar hisobga olinmaydi.",
    count: "Nechta a'zo (birinchi N)",
  },
}
const PRIZES: Record<GiveawayPrize, string> = {
  CODES: "🎁 Promokodlar (sovg'adan)",
  PREMIUM_DAYS: '💎 Premium kunlari',
  PREMIUM_DISCOUNT: '🎟 Premium chegirmasi (%)',
}
const AUDIENCES: Record<GiveawayAudience, string> = {
  ALL: "Barcha faol a'zolar",
  ATTENDED: "Davrda kamida bitta tadbirga kelganlar",
  PREMIUM: "Faqat 💎 Premium a'zolar",
}
const STATUS = {
  DRAFT: { label: 'Qoralama', tone: 'neutral' },
  SCHEDULED: { label: 'Rejada', tone: 'info' },
  DONE: { label: "O'tkazildi", tone: 'success' },
  CANCELLED: { label: 'Bekor qilingan', tone: 'neutral' },
} as const
const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }

function iso(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function monthRange(offset: number): [string, string] {
  const now = new Date()
  const first = new Date(now.getFullYear(), now.getMonth() + offset, 1)
  const last = new Date(now.getFullYear(), now.getMonth() + offset + 1, 0)
  return [iso(first), iso(last)]
}

function GiveawayModal({ giveaway, onClose, onSaved }: { giveaway: Giveaway | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useSession()
  const rewards = useAsync((signal) => api<AdminReward[]>('/api/v1/admin/rewards', { signal }))
  const [thisStart, thisEnd] = monthRange(0)
  const [form, setForm] = useState({
    title: giveaway?.title ?? '',
    prize: giveaway?.prize ?? ('CODES' as GiveawayPrize),
    prize_value: String(giveaway?.prize_value ?? 30),
    reward_id: giveaway?.reward_id ?? '',
    rule: giveaway?.rule ?? ('TEST_TOP' as GiveawayRule),
    audience: giveaway?.audience ?? ('ALL' as GiveawayAudience),
    winners_count: String(giveaway?.winners_count ?? 1),
    premium_bonus: giveaway?.premium_bonus ?? true,
    period_start: giveaway?.period_start ?? thisStart,
    period_end: giveaway?.period_end ?? thisEnd,
    automatic: giveaway ? Boolean(giveaway.scheduled_at) : true,
    scheduled_at: toLocalInput(giveaway?.scheduled_at) || `${thisEnd}T20:00`,
    announce: giveaway?.announce ?? true,
    repeat_monthly: giveaway?.repeat_monthly ?? false,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const rule = RULES[form.rule]
  const activeRewards = rewards.state.status === 'success' ? rewards.state.data.filter((r) => r.status === 'ACTIVE') : []
  const chosen = activeRewards.find((r) => r.id === form.reward_id)

  async function save() {
    setBusy(true)
    setError(null)
    const automatic = form.automatic || form.rule === 'NEW_MEMBERS'
    const body = {
      title: form.title.trim(),
      prize: form.prize,
      prize_value: form.prize === 'CODES' ? null : Number(form.prize_value),
      reward_id: form.prize === 'CODES' ? form.reward_id : null,
      rule: form.rule,
      audience: form.rule === 'EVENT_PLACES' || form.rule === 'NEW_MEMBERS' ? 'ALL' : form.audience,
      winners_count: Number(form.winners_count),
      premium_bonus: form.premium_bonus,
      period_start: form.period_start,
      period_end: form.period_end,
      scheduled_at: automatic ? fromLocalInput(form.scheduled_at) : null,
      announce: form.announce,
      repeat_monthly: automatic && form.repeat_monthly,
    }
    try {
      await api(giveaway ? `/api/v1/admin/giveaways/${giveaway.id}` : '/api/v1/admin/giveaways', { method: giveaway ? 'PATCH' : 'POST', body })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  const presets: [string, [string, string]][] = [
    ['Shu oy', monthRange(0)],
    ["O'tgan oy", monthRange(-1)],
    ['Keyingi oy', monthRange(1)],
  ]

  return (
    <Modal
      title={giveaway ? "O'yinni tahrirlash" : "Yangi sovg'a o'yini"}
      onClose={onClose}
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button
            loading={busy}
            disabled={form.title.trim().length < 3 || (form.prize === 'CODES' ? !form.reward_id : Number(form.prize_value) < 1) || !form.period_start || !form.period_end}
            onClick={() => void save()}
          >
            Saqlash
          </Button>
        </>
      }
    >
      <Field label="Nomi *" hint="A'zolar ko'radi. Masalan: «Oyning eng yaxshi test ishlovchisi»">
        <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={255} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="G'oliblarga nima beriladi">
          <Select value={form.prize} onChange={(e) => setForm({ ...form, prize: e.target.value as GiveawayPrize, prize_value: e.target.value === 'PREMIUM_DISCOUNT' ? '50' : '30' })}>
            {Object.entries(PRIZES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        {form.prize === 'CODES' ? (
          <Field label="Sovg'a (promokodlar) *" hint={chosen ? (chosen.codes_total ? `Bo'sh kodlar: ${chosen.codes_available}` : "Kodsiz sovg'a — qo'lda topshiriladi") : "Avval «🎁 Sovg'alar» bo'limida sovg'a yarating va kodlarni kiriting"}>
            <Select value={form.reward_id} onChange={(e) => setForm({ ...form, reward_id: e.target.value })}>
              <option value="">— tanlang —</option>
              {activeRewards.map((reward) => (
                <option key={reward.id} value={reward.id}>
                  {reward.title}
                  {reward.codes_total ? ` (${reward.codes_available} kod)` : ''}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field
            label={form.prize === 'PREMIUM_DAYS' ? 'Necha kunlik Premium' : 'Chegirma foizi (1–90)'}
            hint={form.prize === 'PREMIUM_DISCOUNT' ? "G'olib 30 kun ichida chegirmali narxda sotib oladi (Stars yoki karta)" : 'Darhol yoqiladi'}
          >
            <Input type="number" min={1} max={form.prize === 'PREMIUM_DAYS' ? 365 : 90} value={form.prize_value} onChange={(e) => setForm({ ...form, prize_value: e.target.value })} />
          </Field>
        )}
        <Field label="Qoida">
          <Select value={form.rule} onChange={(e) => setForm({ ...form, rule: e.target.value as GiveawayRule })}>
            {Object.entries(RULES).map(([value, item]) => (
              <option key={value} value={value}>
                {item.title}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <p className="rounded-lg bg-app-surface px-3 py-2 text-sm text-app-hint">{rule.hint}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={rule.count}>
          <Input type="number" min={1} max={form.rule === 'EVENT_PLACES' ? 10 : 100} value={form.winners_count} onChange={(e) => setForm({ ...form, winners_count: e.target.value })} />
        </Field>
        {form.rule !== 'EVENT_PLACES' && form.rule !== 'NEW_MEMBERS' && (
          <Field label="Kimlar qatnashadi">
            <Select value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value as GiveawayAudience })}>
              {Object.entries(AUDIENCES).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
        )}
      </div>
      {form.rule === 'RANDOM' && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4" checked={form.premium_bonus} onChange={(e) => setForm({ ...form, premium_bonus: e.target.checked })} />
          💎 Premium a'zolarga ikki baravar imkoniyat
        </label>
      )}
      <div className="flex flex-col gap-2">
        <p className="text-sm font-medium">Davr (shu kunlardagi natijalar hisoblanadi)</p>
        <div className="flex flex-wrap gap-2">
          {presets.map(([label, [start, end]]) => (
            <Button key={label} variant={form.period_start === start && form.period_end === end ? 'primary' : 'secondary'} className="px-3 py-1 text-sm" onClick={() => setForm({ ...form, period_start: start, period_end: end, scheduled_at: `${end}T20:00` })}>
              {label}
            </Button>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Boshlanishi">
            <Input type="date" value={form.period_start} onChange={(e) => setForm({ ...form, period_start: e.target.value })} />
          </Field>
          <Field label="Tugashi">
            <Input type="date" value={form.period_end} onChange={(e) => setForm({ ...form, period_end: e.target.value })} />
          </Field>
        </div>
      </div>
      <div className="flex flex-col gap-2 rounded-lg border border-app-border p-3">
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" checked={form.automatic || form.rule === 'NEW_MEMBERS'} onChange={() => setForm({ ...form, automatic: true })} />
          Belgilangan vaqtda <b>avtomatik</b> o'tkazilsin
        </label>
        {(form.automatic || form.rule === 'NEW_MEMBERS') && (
          <div className="flex flex-col gap-2 pl-6">
            <Input type="datetime-local" value={form.scheduled_at} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })} />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={form.repeat_monthly} onChange={(e) => setForm({ ...form, repeat_monthly: e.target.checked })} />
              🔁 Har oy takrorlansin (keyingi oy o'zi rejalashtiriladi)
            </label>
          </div>
        )}
        {form.rule === 'NEW_MEMBERS' ? (
          <p className="text-xs text-app-hint">Bu qoida doim avtomatik: a'zolar qo'shilishi bilan sovg'a oladi, davr oxirida o'yin yopiladi.</p>
        ) : (
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" checked={!form.automatic} onChange={() => setForm({ ...form, automatic: false })} />
            O'zim «O'tkazish» tugmasini bosaman
          </label>
        )}
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="size-4" checked={form.announce} onChange={(e) => setForm({ ...form, announce: e.target.checked })} />
        📢 G'oliblar barcha a'zolarga (va kanalga) e'lon qilinsin
      </label>
      <InlineError message={error} />
    </Modal>
  )
}

function Winners({ winners, showFull }: { winners: Giveaway['winners']; showFull: boolean }) {
  return (
    <Table head={['', "A'zo", 'Sabab', '']}>
      {winners.length === 0 && <EmptyRow colSpan={4} text="G'olib yo'q" />}
      {winners.map((winner, index) => (
        <tr key={`${winner.user_id}-${index}`}>
          <td className="px-4 py-2">{winner.place && winner.place <= 3 ? MEDALS[winner.place] : '🎁'}</td>
          <td className="px-4 py-2 font-medium">{showFull ? (winner.full_name ?? winner.name) : winner.name}</td>
          <td className="px-4 py-2 text-sm">{winner.reason}</td>
          <td className="px-4 py-2 text-sm text-app-danger">{winner.error ?? ''}</td>
        </tr>
      ))}
    </Table>
  )
}

function GiveawayDetail({ giveaway, onClose, onChanged }: { giveaway: Giveaway; onClose: () => void; onChanged: () => void }) {
  const { api } = useSession()
  const open = giveaway.status === 'DRAFT' || giveaway.status === 'SCHEDULED'
  const preview = useAsync(
    (signal) => (open ? api<GiveawayPreview>(`/api/v1/admin/giveaways/${giveaway.id}/preview`, { signal }) : Promise.resolve(null)),
    [giveaway.id, open],
  )
  const [current, setCurrent] = useState(giveaway)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function act(path: 'draw' | 'cancel', question: string) {
    if (!window.confirm(question)) return
    setBusy(true)
    setError(null)
    try {
      setCurrent(await api<Giveaway>(`/api/v1/admin/giveaways/${giveaway.id}/${path}`, { method: 'POST' }))
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bajarib bo\'lmadi.')
    } finally {
      setBusy(false)
    }
  }

  const stillOpen = current.status === 'DRAFT' || current.status === 'SCHEDULED'
  const data = preview.state.status === 'success' ? preview.state.data : null
  return (
    <Modal
      title={current.title}
      onClose={onClose}
      wide
      footer={
        stillOpen ? (
          <>
            <Button variant="ghost" className="text-app-danger" disabled={busy} onClick={() => void act('cancel', "O'yinni bekor qilasizmi?")}>
              Bekor qilish
            </Button>
            <Button loading={busy} onClick={() => void act('draw', "G'oliblar hozir aniqlanib, kodlar darhol beriladi. Davom etasizmi?")}>
              🎲 Hozir o'tkazish
            </Button>
          </>
        ) : undefined
      }
    >
      <div className="grid gap-2 text-sm sm:grid-cols-2">
        <p>
          <span className="text-app-hint">Sovg'a:</span> {current.reward_title}
          {current.codes_available !== null && <span className="text-app-hint"> ({current.codes_available} bo'sh kod)</span>}
        </p>
        <p>
          <span className="text-app-hint">Qoida:</span> {RULES[current.rule].title}
        </p>
        <p>
          <span className="text-app-hint">Davr:</span> {current.period_label}
        </p>
        <p>
          <span className="text-app-hint">Holat:</span> <Badge tone={STATUS[current.status].tone}>{STATUS[current.status].label}</Badge>{' '}
          {current.status === 'SCHEDULED' && formatDateTime(current.scheduled_at)}
          {current.status === 'DONE' && formatDateTime(current.drawn_at)}
          {current.repeat_monthly && ' · 🔁 har oy'}
        </p>
      </div>
      <InlineError message={error} />
      {stillOpen ? (
        <div className="flex flex-col gap-2">
          <h3 className="font-semibold">Hozir o'tkazilsa</h3>
          {preview.state.status === 'loading' && <LoadingState />}
          {preview.state.status === 'error' && <ErrorState message={preview.state.error.message} onRetry={preview.reload} />}
          {data && (
            <>
              {current.rule === 'RANDOM' ? (
                <p className="text-sm">
                  Qatnashuvchilar: <b>{data.eligible}</b> a'zo{data.premium > 0 && current.premium_bonus && <> (shundan 💎 {data.premium} tasi ikki baravar imkoniyat bilan)</>}. G'oliblar o'tkazilganda tasodifiy tanlanadi.
                </p>
              ) : (
                <Winners winners={data.winners} showFull />
              )}
              {data.notes.map((note) => (
                <p key={note} className="text-sm text-amber-700 dark:text-amber-400">
                  ⚠️ {note}
                </p>
              ))}
            </>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <h3 className="font-semibold">G'oliblar</h3>
          <Winners winners={current.winners} showFull />
          {current.seed && <p className="text-xs text-app-hint">Tasodif kaliti (shaffoflik uchun): <span className="font-mono">{current.seed}</span></p>}
        </div>
      )}
    </Modal>
  )
}

export function GiveawaysPage() {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<Giveaway[]>('/api/v1/admin/giveaways', { signal }))
  const [editing, setEditing] = useState<Giveaway | 'new' | null>(null)
  const [open, setOpen] = useState<Giveaway | null>(null)

  return (
    <>
      <PageHeader
        title="Sovg'a o'yinlari"
        subtitle="Promokodlarni adolatli qoida bo'yicha tarqatish: tasodifiy g'oliblar, oyning eng yaxshi test ishlovchisi, har bir tadbirning 1-2-3-o'rinlari. Belgilangan vaqtda o'zi o'tadi."
        actions={<Button onClick={() => setEditing('new')}>+ Yangi o'yin</Button>}
      />
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={["O'yin", 'Qoida', 'Davr', 'Holat', "G'oliblar", '']}>
            {state.data.length === 0 && <EmptyRow colSpan={6} text="Hali o'yin yo'q. «+ Yangi o'yin» tugmasini bosing." />}
            {state.data.map((giveaway) => (
              <tr key={giveaway.id} className={giveaway.status === 'CANCELLED' ? 'text-app-hint' : ''}>
                <td className="min-w-[16rem] px-4 py-2.5">
                  <p className="font-medium">{giveaway.title}</p>
                  <p className="text-xs text-app-hint">
                    {giveaway.prize === 'CODES' ? '🎁 ' : ''}
                    {giveaway.reward_title}
                    {giveaway.codes_available !== null && ` · ${giveaway.codes_available} bo'sh kod`}
                  </p>
                </td>
                <td className="min-w-[11rem] px-4 py-2.5 text-sm">{RULES[giveaway.rule].title}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm">{giveaway.period_label}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm">
                  <Badge tone={STATUS[giveaway.status].tone}>{STATUS[giveaway.status].label}</Badge>
                  {giveaway.status === 'SCHEDULED' && <p className="mt-1 text-xs text-app-hint">{formatDateTime(giveaway.scheduled_at)}{giveaway.repeat_monthly && ' · 🔁'}</p>}
                </td>
                <td className="px-4 py-2.5 tabular-nums">{giveaway.status === 'DONE' ? giveaway.winners.filter((w) => !w.error).length : `${giveaway.winners_count}${giveaway.rule === 'EVENT_PLACES' ? ' / tadbir' : ''}`}</td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  <Button variant="ghost" onClick={() => setOpen(giveaway)}>
                    {giveaway.status === 'DONE' ? 'Natijalar' : 'Ochish'}
                  </Button>
                  {(giveaway.status === 'DRAFT' || giveaway.status === 'SCHEDULED') && (
                    <Button variant="ghost" onClick={() => setEditing(giveaway)}>
                      Tahrirlash
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {editing && (
        <GiveawayModal
          giveaway={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            reload()
          }}
        />
      )}
      {open && <GiveawayDetail giveaway={open} onClose={() => setOpen(null)} onChanged={reload} />}
    </>
  )
}
