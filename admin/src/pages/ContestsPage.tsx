import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminReward, Faculty } from '../types/api'
import { formatDateTime, fromLocalInput, toLocalInput } from '../utils/format'

type Rule = 'REGISTERED' | 'ATTENDED' | 'POINTS'
type NameFormat = 'FULL' | 'SHORT' | 'HIDDEN'

interface Prize {
  place: number
  points: number
  premium_days: number
  reward_id: string | null
  text: string | null
}

interface Contest {
  id: string
  title: string
  description: string | null
  starts_at: string
  ends_at: string
  status: string
  state: 'draft' | 'upcoming' | 'running' | 'finished' | 'cancelled'
  rule: Rule
  rule_text: string
  min_friend_points: number
  min_friends: number
  winners_count: number
  prizes: Prize[]
  participation_points: number
  faculty_id: string | null
  course: number | null
  show_leaderboard: boolean
  leaderboard_size: number
  show_counts: boolean
  name_format: NameFormat
  show_my_place: boolean
  show_prizes: boolean
  freeze_hours: number
  announce: boolean
  remind_hours: number
  announce_results: boolean
  post_to_channel: boolean
  announced_at: string | null
  finished_at: string | null
  excluded: { user_id: string; reason: string }[]
  results: ContestResult[] | null
}

interface ContestResult {
  place: number
  user_id: string
  name: string
  friends: number
  winner: boolean
  prize: Prize | null
  handed_over: boolean
  given?: { points?: number; premium_days?: number; reward_id?: string; error?: string }
}

interface Standing {
  place: number
  user_id: string
  name: string
  faculty: string | null
  group_name: string | null
  friends: number
  winner: boolean
}

interface Friend {
  user_id: string
  name: string
  phone: string | null
  joined_at: string | null
  status: string
  came_to_event: boolean
  points: number
  counts: boolean
}

interface Inviter {
  place: number
  user_id: string
  name: string
  group_name: string | null
  faculty: string | null
  registered: number
  attended: number
}

const RULES: Record<Rule, { title: string; hint: string }> = {
  ATTENDED: {
    title: "✅ Tadbirga kelgan do'stlar (tavsiya)",
    hint: "Do'st havola orqali tanlov davrida qo'shilib, tanlov tugaguncha kamida bitta tadbirga kelishi kerak. Soxta akkauntlardan eng yaxshi himoya.",
  },
  REGISTERED: {
    title: "👤 Ro'yxatdan o'tgan do'stlar",
    hint: "Havola orqali tanlov davrida ro'yxatdan o'tgan har bir faol do'st sanaladi. Tez va oson, lekin soxta akkauntlar xavfi bor — jadvalni tekshirib turing.",
  },
  POINTS: {
    title: "⭐ Ball to'plagan do'stlar",
    hint: "Do'st tanlov tugaguncha kamida N ball to'plashi kerak (tadbir, test, kitob). Eng faol yangi kitobxonlarni rag'batlantiradi.",
  },
}
const NAME_FORMATS: Record<NameFormat, string> = {
  SHORT: 'Ism va familiya harfi (Aziza K.)',
  FULL: "To'liq ism (Aziza Karimova)",
  HIDDEN: "Yashirin («Ishtirokchi»; o'zini «Siz» deb ko'radi)",
}
const STATE: Record<Contest['state'], { label: string; tone: 'neutral' | 'info' | 'success' | 'warning' }> = {
  draft: { label: 'Qoralama', tone: 'neutral' },
  upcoming: { label: 'E\'lon qilingan, boshlanmagan', tone: 'info' },
  running: { label: 'Davom etmoqda', tone: 'success' },
  finished: { label: 'Yakunlangan', tone: 'neutral' },
  cancelled: { label: 'Bekor qilingan', tone: 'warning' },
}
const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }
const LOCKED_WHILE_RUNNING = ['starts_at', 'rule', 'min_friend_points', 'min_friends', 'winners_count', 'prizes', 'participation_points', 'faculty_id', 'course', 'announce']

function emptyPrize(place: number): Prize {
  return { place, points: 0, premium_days: 0, reward_id: null, text: null }
}

function inDays(days: number, hour: number): string {
  const date = new Date(Date.now() + days * 86_400_000)
  date.setUTCHours(hour - 5, 0, 0, 0)
  return toLocalInput(date.toISOString())
}

function prizeLabel(prize: Prize | null, rewards: AdminReward[]): string {
  if (!prize) return '—'
  const parts = [
    prize.points ? `+${prize.points} ball` : null,
    prize.premium_days ? `${prize.premium_days} kun 💎` : null,
    prize.reward_id ? `🎁 ${rewards.find((r) => r.id === prize.reward_id)?.title ?? "sovg'a"}` : null,
    prize.text,
  ]
  return parts.filter(Boolean).join(' + ') || '—'
}

function Check({ checked, onChange, label, hint, disabled }: { checked: boolean; onChange: (value: boolean) => void; label: string; hint?: string; disabled?: boolean }) {
  return (
    <label className={`flex items-start gap-2 text-sm ${disabled ? 'opacity-50' : ''}`}>
      <input type="checkbox" className="mt-1" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span>
        {label}
        {hint && <span className="block text-xs text-app-hint">{hint}</span>}
      </span>
    </label>
  )
}

function ContestModal({ contest, onClose, onSaved }: { contest: Contest | null; onClose: () => void; onSaved: () => void }) {
  const { api } = useSession()
  const rewards = useAsync((signal) => api<AdminReward[]>('/api/v1/admin/rewards', { signal }))
  const faculties = useAsync((signal) => api<Faculty[]>('/api/v1/admin/faculties', { signal }))
  const running = contest !== null && (contest.state === 'running' || (contest.state === 'upcoming' && new Date(contest.starts_at) <= new Date()))
  const [form, setForm] = useState({
    title: contest?.title ?? '',
    description: contest?.description ?? '',
    starts_at: toLocalInput(contest?.starts_at) || inDays(0, 9),
    ends_at: toLocalInput(contest?.ends_at) || inDays(30, 20),
    rule: contest?.rule ?? ('ATTENDED' as Rule),
    min_friend_points: String(contest?.min_friend_points ?? 20),
    min_friends: String(contest?.min_friends ?? 1),
    winners_count: String(contest?.winners_count ?? 3),
    prizes: contest?.prizes?.length ? contest.prizes : [emptyPrize(1), emptyPrize(2), emptyPrize(3)],
    participation_points: String(contest?.participation_points ?? 0),
    faculty_id: contest?.faculty_id ?? '',
    course: contest?.course ? String(contest.course) : '',
    show_leaderboard: contest?.show_leaderboard ?? true,
    leaderboard_size: String(contest?.leaderboard_size ?? 10),
    show_counts: contest?.show_counts ?? true,
    name_format: contest?.name_format ?? ('SHORT' as NameFormat),
    show_my_place: contest?.show_my_place ?? true,
    show_prizes: contest?.show_prizes ?? true,
    freeze_hours: String(contest?.freeze_hours ?? 0),
    announce: contest?.announce ?? true,
    remind_hours: String(contest?.remind_hours ?? 24),
    announce_results: contest?.announce_results ?? true,
    post_to_channel: contest?.post_to_channel ?? false,
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const activeRewards = rewards.state.status === 'success' ? rewards.state.data.filter((r) => r.status === 'ACTIVE') : []
  const winners = Math.max(1, Math.min(50, Number(form.winners_count) || 1))

  function prizeAt(place: number): Prize {
    return form.prizes.find((p) => p.place === place) ?? emptyPrize(place)
  }

  function setPrize(place: number, changes: Partial<Prize>) {
    const others = form.prizes.filter((p) => p.place !== place)
    setForm({ ...form, prizes: [...others, { ...prizeAt(place), ...changes }].sort((a, b) => a.place - b.place) })
  }

  async function save() {
    setBusy(true)
    setError(null)
    const body: Record<string, unknown> = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      starts_at: fromLocalInput(form.starts_at),
      ends_at: fromLocalInput(form.ends_at),
      rule: form.rule,
      min_friend_points: Number(form.min_friend_points) || 0,
      min_friends: Number(form.min_friends) || 1,
      winners_count: winners,
      prizes: form.prizes
        .filter((p) => p.place <= winners)
        .map((p) => ({ ...p, reward_id: p.reward_id || null, text: p.text?.trim() || null })),
      participation_points: Number(form.participation_points) || 0,
      faculty_id: form.faculty_id || null,
      course: form.course ? Number(form.course) : null,
      show_leaderboard: form.show_leaderboard,
      leaderboard_size: Number(form.leaderboard_size) || 0,
      show_counts: form.show_counts,
      name_format: form.name_format,
      show_my_place: form.show_my_place,
      show_prizes: form.show_prizes,
      freeze_hours: Number(form.freeze_hours) || 0,
      announce: form.announce,
      remind_hours: Number(form.remind_hours) || 0,
      announce_results: form.announce_results,
      post_to_channel: form.post_to_channel,
    }
    if (running) for (const key of LOCKED_WHILE_RUNNING) delete body[key]
    try {
      await api(contest ? `/api/v1/admin/referral-contests/${contest.id}` : '/api/v1/admin/referral-contests', {
        method: contest ? 'PATCH' : 'POST',
        body,
      })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      title={contest ? 'Tanlovni tahrirlash' : 'Yangi taklif tanlovi'}
      onClose={onClose}
      wide
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button loading={busy} disabled={form.title.trim().length < 3 || !form.starts_at || !form.ends_at} onClick={() => void save()}>
            Saqlash
          </Button>
        </>
      }
    >
      {running && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Tanlov boshlangan: adolat uchun shartlar va sovrinlar qulflangan. Nomi, tavsifi, ko'rinish sozlamalari va tugash vaqtini
          o'zgartirish mumkin.
        </p>
      )}
      <Field label="Nomi *" hint="Masalan: «Oktabr: kim ko'p do'st olib keladi?»">
        <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={255} />
      </Field>
      <Field label="Tavsif" hint="Shartlar, qiziqarli gaplar — e'londa va ilovada ko'rinadi">
        <Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={2000} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Boshlanishi (Toshkent vaqti)">
          <Input type="datetime-local" value={form.starts_at} disabled={running} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} />
        </Field>
        <Field label="Tugashi">
          <Input type="datetime-local" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} />
        </Field>
      </div>

      <h3 className="pt-2 font-semibold">📏 Qoidalar</h3>
      <Field label="Qaysi do'stlar sanaladi">
        <Select value={form.rule} disabled={running} onChange={(e) => setForm({ ...form, rule: e.target.value as Rule })}>
          {Object.entries(RULES).map(([value, item]) => (
            <option key={value} value={value}>
              {item.title}
            </option>
          ))}
        </Select>
      </Field>
      <p className="rounded-lg bg-app-surface px-3 py-2 text-sm text-app-hint">{RULES[form.rule].hint}</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {form.rule === 'POINTS' && (
          <Field label="Do'st kamida necha ball to'plasin">
            <Input type="number" min={1} max={10000} disabled={running} value={form.min_friend_points} onChange={(e) => setForm({ ...form, min_friend_points: e.target.value })} />
          </Field>
        )}
        <Field label="G'olib bo'lish uchun kamida necha do'st" hint="Bundan kam bo'lsa sovrin berilmaydi">
          <Input type="number" min={1} max={1000} disabled={running} value={form.min_friends} onChange={(e) => setForm({ ...form, min_friends: e.target.value })} />
        </Field>
        <Field label="Sovrinli o'rinlar soni">
          <Input type="number" min={1} max={50} disabled={running} value={form.winners_count} onChange={(e) => setForm({ ...form, winners_count: e.target.value })} />
        </Field>
        <Field label="Qatnashuvchilar" hint="Adminlar hech qachon qatnashmaydi">
          <Select value={form.faculty_id} disabled={running} onChange={(e) => setForm({ ...form, faculty_id: e.target.value })}>
            <option value="">Barcha fakultetlar</option>
            {faculties.state.status === 'success' &&
              faculties.state.data.map((faculty) => (
                <option key={faculty.id} value={faculty.id}>
                  {faculty.name}
                </option>
              ))}
          </Select>
        </Field>
        <Field label="Kurs">
          <Select value={form.course} disabled={running} onChange={(e) => setForm({ ...form, course: e.target.value })}>
            <option value="">Barcha kurslar</option>
            {[1, 2, 3, 4, 5, 6].map((course) => (
              <option key={course} value={course}>
                {course}-kurs
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <h3 className="pt-2 font-semibold">🎁 Sovrinlar</h3>
      <p className="text-sm text-app-hint">
        Har bir o'ringa bir yoki bir nechta sovrin: ball, Premium kunlar, promokod («🎁 Sovg'alar»dagi sovg'adan) yoki qo'lda
        topshiriladigan sovg'a (masalan, kitob). Ball, Premium va promokod tanlov tugashi bilan avtomatik beriladi.
      </p>
      <div className="flex flex-col gap-2">
        {Array.from({ length: winners }, (_, index) => index + 1).map((place) => {
          const prize = prizeAt(place)
          return (
            <div key={place} className="grid items-end gap-2 rounded-lg border border-app-border p-3 sm:grid-cols-[3rem_6rem_6rem_1fr_1fr]">
              <span className="pb-2 text-lg font-semibold">{MEDALS[place] ?? `${place}.`}</span>
              <Field label="Ball">
                <Input type="number" min={0} max={10000} disabled={running} value={prize.points || ''} onChange={(e) => setPrize(place, { points: Number(e.target.value) || 0 })} />
              </Field>
              <Field label="Premium kun">
                <Input type="number" min={0} max={366} disabled={running} value={prize.premium_days || ''} onChange={(e) => setPrize(place, { premium_days: Number(e.target.value) || 0 })} />
              </Field>
              <Field label="Promokod (sovg'a)">
                <Select value={prize.reward_id ?? ''} disabled={running} onChange={(e) => setPrize(place, { reward_id: e.target.value || null })}>
                  <option value="">—</option>
                  {activeRewards.map((reward) => (
                    <option key={reward.id} value={reward.id}>
                      {reward.title}
                      {reward.codes_total ? ` (${reward.codes_available} kod)` : ''}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Qo'lda beriladigan sovg'a">
                <Input value={prize.text ?? ''} disabled={running} maxLength={200} placeholder="Masalan: «O'tkan kunlar» kitobi" onChange={(e) => setPrize(place, { text: e.target.value })} />
              </Field>
            </div>
          )
        })}
      </div>
      <Field label="Shartni bajargan har bir ishtirokchiga ball (ixtiyoriy)" hint="«Kamida N do'st» shartini bajarganlarning hammasiga — g'oliblarga ham">
        <Input type="number" min={0} max={1000} disabled={running} value={form.participation_points} onChange={(e) => setForm({ ...form, participation_points: e.target.value })} />
      </Field>

      <h3 className="pt-2 font-semibold">👁 A'zolar nimani ko'radi</h3>
      <div className="grid gap-2 sm:grid-cols-2">
        <Check checked={form.show_leaderboard} onChange={(v) => setForm({ ...form, show_leaderboard: v })} label="Jadvalni ko'rsatish" hint="O'chirilsa — faqat o'z natijasini ko'radi" />
        <Check checked={form.show_counts} onChange={(v) => setForm({ ...form, show_counts: v })} label="Jadvalda do'stlar sonini ko'rsatish" hint="O'chirilsa — faqat o'rinlar ko'rinadi" />
        <Check checked={form.show_my_place} onChange={(v) => setForm({ ...form, show_my_place: v })} label="Har kimga o'z o'rnini ko'rsatish" />
        <Check checked={form.show_prizes} onChange={(v) => setForm({ ...form, show_prizes: v })} label="Sovrinlarni oldindan ko'rsatish" hint="O'chirilsa — sovrinlar sir saqlanadi" />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Jadvalda nechta o'rin">
          <Input type="number" min={0} max={100} value={form.leaderboard_size} onChange={(e) => setForm({ ...form, leaderboard_size: e.target.value })} />
        </Field>
        <Field label="Ismlar">
          <Select value={form.name_format} onChange={(e) => setForm({ ...form, name_format: e.target.value as NameFormat })}>
            {Object.entries(NAME_FORMATS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Oxirgi necha soatda jadval yashiriladi" hint="Intriga uchun; 0 — yashirilmaydi">
          <Input type="number" min={0} max={168} value={form.freeze_hours} onChange={(e) => setForm({ ...form, freeze_hours: e.target.value })} />
        </Field>
      </div>

      <h3 className="pt-2 font-semibold">📢 Xabarlar</h3>
      <div className="grid gap-2 sm:grid-cols-2">
        <Check checked={form.announce} disabled={running} onChange={(v) => setForm({ ...form, announce: v })} label="Boshlanganda hammaga e'lon" hint="Sovrinlar va havola tugmasi bilan" />
        <Check checked={form.announce_results} onChange={(v) => setForm({ ...form, announce_results: v })} label="Natijalarni hammaga e'lon qilish" />
        <Check checked={form.post_to_channel} onChange={(v) => setForm({ ...form, post_to_channel: v })} label="Natijalarni kanalga post qilish" />
      </div>
      <Field label="Tugashidan necha soat oldin eslatma" hint="Ishtirokchilarga o'rni va kerakli do'stlar soni bilan; 0 — eslatmasiz">
        <Input type="number" min={0} max={168} value={form.remind_hours} onChange={(e) => setForm({ ...form, remind_hours: e.target.value })} />
      </Field>
      <InlineError message={error} />
    </Modal>
  )
}

function FriendsModal({ contest, standing, onClose }: { contest: Contest; standing: Standing; onClose: () => void }) {
  const { api } = useSession()
  const friends = useAsync(
    (signal) => api<Friend[]>(`/api/v1/admin/referral-contests/${contest.id}/participants/${standing.user_id}/friends`, { signal }),
    [standing.user_id],
  )
  return (
    <Modal title={`${standing.name}: olib kelgan do'stlari`} onClose={onClose} wide>
      {friends.state.status === 'loading' && <LoadingState />}
      {friends.state.status === 'error' && <ErrorState message={friends.state.error.message} />}
      {friends.state.status === 'success' && (
        <Table head={['Ism', 'Telefon', "Qo'shilgan", 'Tadbir', 'Ball', 'Sanaladi']}>
          {friends.state.data.length === 0 && <EmptyRow colSpan={6} text="Do'stlar yo'q" />}
          {friends.state.data.map((friend) => (
            <tr key={friend.user_id}>
              <td className="px-4 py-2">{friend.name}</td>
              <td className="px-4 py-2 tabular-nums">{friend.phone ?? '—'}</td>
              <td className="px-4 py-2">{formatDateTime(friend.joined_at)}</td>
              <td className="px-4 py-2">{friend.came_to_event ? '✅' : '—'}</td>
              <td className="px-4 py-2 tabular-nums">{friend.points}</td>
              <td className="px-4 py-2">{friend.counts ? <Badge tone="success">ha</Badge> : <Badge>yo'q</Badge>}</td>
            </tr>
          ))}
        </Table>
      )}
      <p className="text-xs text-app-hint">
        Shubhali (bir xil, faol bo'lmagan) akkauntlarni «👥 A'zolar» bo'limida bloklasangiz, ular jadvaldan o'zi chiqadi.
      </p>
    </Modal>
  )
}

function ContestDetails({ contest, rewards, onChanged }: { contest: Contest; rewards: AdminReward[]; onChanged: () => void }) {
  const { api } = useSession()
  const showTable = contest.state === 'running' || contest.state === 'upcoming' || contest.state === 'draft'
  const standings = useAsync(
    (signal) => (showTable ? api<Standing[]>(`/api/v1/admin/referral-contests/${contest.id}/standings`, { signal }) : Promise.resolve([])),
    [contest.id, contest.excluded.length, contest.state],
  )
  const [friendsOf, setFriendsOf] = useState<Standing | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  async function act(key: string, path: string, body?: unknown) {
    setBusy(key)
    setError(null)
    try {
      await api(path, { method: 'POST', body })
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bajarib bo'lmadi.")
    } finally {
      setBusy(null)
    }
  }

  const base = `/api/v1/admin/referral-contests/${contest.id}`
  return (
    <div className="flex flex-col gap-3 border-t border-app-border pt-3">
      <InlineError message={error} />
      <div className="flex flex-wrap gap-2">
        {contest.state === 'draft' && (
          <Button loading={busy === 'publish'} onClick={() => void act('publish', `${base}/publish`)}>
            📢 E'lon qilish
          </Button>
        )}
        {(contest.state === 'running' || contest.state === 'upcoming') && (
          <Button
            variant="secondary"
            loading={busy === 'finish'}
            onClick={() => window.confirm("Tanlovni hozir yakunlab, g'oliblarga sovrin berilsinmi?") && void act('finish', `${base}/finish`)}
          >
            🏁 Hozir yakunlash
          </Button>
        )}
        {contest.state !== 'finished' && contest.state !== 'cancelled' && (
          <Button
            variant="ghost"
            loading={busy === 'cancel'}
            onClick={() => {
              const reason = window.prompt('Bekor qilish sababi (a\'zolarga yuboriladi, ixtiyoriy):', '')
              if (reason !== null) void act('cancel', `${base}/cancel`, { reason })
            }}
          >
            Bekor qilish
          </Button>
        )}
      </div>

      {showTable && (
        <>
          <h3 className="font-semibold">📊 Jadval (adminlar hammasini ko'radi)</h3>
          {standings.state.status === 'loading' && <LoadingState />}
          {standings.state.status === 'success' && (
            <Table head={["O'rin", 'Ism', 'Fakultet / guruh', "Do'stlar", '']}>
              {standings.state.data.length === 0 && <EmptyRow colSpan={5} text="Hali hech kim yo'q" />}
              {standings.state.data.map((row) => (
                <tr key={row.user_id}>
                  <td className="px-4 py-2 font-semibold">{MEDALS[row.place] ?? row.place}</td>
                  <td className="px-4 py-2">
                    {row.name} {row.winner && <Badge tone="success">sovrinli</Badge>}
                  </td>
                  <td className="px-4 py-2 text-app-hint">{[row.faculty, row.group_name].filter(Boolean).join(' · ') || '—'}</td>
                  <td className="px-4 py-2 font-semibold tabular-nums">{row.friends}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-right">
                    <Button variant="ghost" onClick={() => setFriendsOf(row)}>
                      Do'stlari
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        const reason = window.prompt('Jadvaldan chiqarish sababi:', 'Soxta akkauntlar')
                        if (reason) void act(`ex:${row.user_id}`, `${base}/participants/${row.user_id}/exclude`, { reason })
                      }}
                    >
                      Chiqarish
                    </Button>
                  </td>
                </tr>
              ))}
            </Table>
          )}
          {contest.excluded.length > 0 && (
            <div className="text-sm">
              <p className="font-medium">Jadvaldan chiqarilganlar:</p>
              {contest.excluded.map((item) => (
                <p key={item.user_id} className="flex items-center gap-2 text-app-hint">
                  {item.reason}
                  <Button variant="ghost" onClick={() => void act(`in:${item.user_id}`, `${base}/participants/${item.user_id}/include`)}>
                    Qaytarish
                  </Button>
                </p>
              ))}
            </div>
          )}
        </>
      )}

      {contest.results && (
        <>
          <h3 className="font-semibold">🏆 Natijalar</h3>
          <Table head={["O'rin", 'Ism', "Do'stlar", 'Sovrin', 'Holati']}>
            {contest.results.length === 0 && <EmptyRow colSpan={5} text="Shartni bajargan ishtirokchi bo'lmadi" />}
            {contest.results.map((item) => (
              <tr key={item.user_id}>
                <td className="px-4 py-2 font-semibold">{MEDALS[item.place] ?? item.place}</td>
                <td className="px-4 py-2">{item.name}</td>
                <td className="px-4 py-2 tabular-nums">{item.friends}</td>
                <td className="px-4 py-2">{item.winner ? prizeLabel(item.prize, rewards) : contest.participation_points ? `+${contest.participation_points} ball` : '—'}</td>
                <td className="px-4 py-2">
                  {item.given?.error && <Badge tone="warning">{item.given.error}</Badge>}
                  {item.winner && !item.handed_over ? (
                    <Button variant="ghost" loading={busy === `h:${item.user_id}`} onClick={() => void act(`h:${item.user_id}`, `${base}/winners/${item.user_id}/handed-over`)}>
                      ✅ Topshirildi deb belgilash
                    </Button>
                  ) : item.winner ? (
                    <Badge tone="success">berildi</Badge>
                  ) : null}
                </td>
              </tr>
            ))}
          </Table>
        </>
      )}
      {friendsOf && <FriendsModal contest={contest} standing={friendsOf} onClose={() => setFriendsOf(null)} />}
    </div>
  )
}

function TopInviters() {
  const { api } = useSession()
  const [rule, setRule] = useState<'ATTENDED' | 'REGISTERED'>('ATTENDED')
  const top = useAsync((signal) => api<Inviter[]>(`/api/v1/admin/referral-contests/top-inviters?rule=${rule}&limit=50`, { signal }), [rule])
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">👥 Barcha vaqt: eng ko'p do'st olib kelganlar</h2>
          <p className="text-sm text-app-hint">A'zolarga ko'rinadigan ro'yxat — «Sozlamalar» → referral.leaderboard_size</p>
        </div>
        <Select value={rule} onChange={(e) => setRule(e.target.value as 'ATTENDED' | 'REGISTERED')}>
          <option value="ATTENDED">Tadbirga kelganlar bo'yicha</option>
          <option value="REGISTERED">Ro'yxatdan o'tganlar bo'yicha</option>
        </Select>
      </div>
      {top.state.status === 'success' && (
        <Table head={['#', 'Ism', 'Fakultet / guruh', "Ro'yxatdan o'tgan", 'Tadbirga kelgan']}>
          {top.state.data.length === 0 && <EmptyRow colSpan={5} text="Hali taklif qilinganlar yo'q" />}
          {top.state.data.map((row) => (
            <tr key={row.user_id}>
              <td className="px-4 py-2 font-semibold">{MEDALS[row.place] ?? row.place}</td>
              <td className="px-4 py-2">{row.name}</td>
              <td className="px-4 py-2 text-app-hint">{[row.faculty, row.group_name].filter(Boolean).join(' · ') || '—'}</td>
              <td className="px-4 py-2 tabular-nums">{row.registered}</td>
              <td className="px-4 py-2 tabular-nums">{row.attended}</td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  )
}

/** «🏁 Taklif tanlovlari»: «kim ko'p do'st olib kelsa — sovg'a» contests with every setting. */
export function ContestsPage() {
  const { api } = useSession()
  const contests = useAsync((signal) => api<Contest[]>('/api/v1/admin/referral-contests', { signal }))
  const rewards = useAsync((signal) => api<AdminReward[]>('/api/v1/admin/rewards', { signal }))
  const [editing, setEditing] = useState<Contest | null | 'new'>(null)
  const [open, setOpen] = useState<string | null>(null)
  const rewardList = rewards.state.status === 'success' ? rewards.state.data : []

  return (
    <>
      <PageHeader
        title="Taklif tanlovlari"
        subtitle="«Kim belgilangan muddatda klubga eng ko'p do'st olib kelsa — sovg'a». Shartlar, har bir o'rin sovrini, a'zolar nimani ko'rishi — hammasini shu yerda sozlaysiz."
        actions={<Button onClick={() => setEditing('new')}>+ Yangi tanlov</Button>}
      />
      {contests.state.status === 'loading' && <LoadingState />}
      {contests.state.status === 'error' && <ErrorState message={contests.state.error.message} onRetry={contests.reload} />}
      {contests.state.status === 'success' && (
        <div className="flex flex-col gap-3">
          {contests.state.data.length === 0 && (
            <Card className="p-6 text-center text-app-hint">
              Hali tanlov yo'q. «+ Yangi tanlov» — masalan, «Oktabr oxirigacha eng ko'p do'st olib kelgan 3 kishiga sovg'a».
            </Card>
          )}
          {contests.state.data.map((contest) => (
            <Card key={contest.id} className="flex flex-col gap-2 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-semibold">
                    🏁 {contest.title} <Badge tone={STATE[contest.state].tone}>{STATE[contest.state].label}</Badge>
                  </p>
                  <p className="text-sm text-app-hint">
                    {formatDateTime(contest.starts_at)} — {formatDateTime(contest.ends_at)} · {contest.rule_text}
                    {contest.min_friends > 1 ? ` (kamida ${contest.min_friends} ta)` : ''}
                  </p>
                  <p className="text-sm">
                    {Array.from({ length: contest.winners_count }, (_, i) => i + 1)
                      .map((place) => `${MEDALS[place] ?? `${place}.`} ${prizeLabel(contest.prizes.find((p) => p.place === place) ?? null, rewardList)}`)
                      .join('   ')}
                  </p>
                </div>
                <div className="flex gap-2">
                  {(contest.state === 'draft' || contest.state === 'upcoming' || contest.state === 'running') && (
                    <Button variant="secondary" onClick={() => setEditing(contest)}>
                      ✏️ Tahrirlash
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => setOpen(open === contest.id ? null : contest.id)}>
                    {open === contest.id ? 'Yopish' : 'Batafsil'}
                  </Button>
                </div>
              </div>
              {open === contest.id && <ContestDetails contest={contest} rewards={rewardList} onChanged={contests.reload} />}
            </Card>
          ))}
        </div>
      )}
      <div className="mt-4">
        <TopInviters />
      </div>
      {editing && (
        <ContestModal
          contest={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            contests.reload()
          }}
        />
      )}
    </>
  )
}
