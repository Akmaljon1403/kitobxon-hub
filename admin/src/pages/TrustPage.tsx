import { useState, type ReactNode } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, InlineError, Input, PageHeader, Select, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import { formatDate, formatDateTime } from '../utils/format'

interface Trust {
  days: number
  fast_tests: { member: string; test: string; score: number; max_score: number; seconds: number; allowed_minutes: number; submitted_at: string }[]
  manual_members: { member: string; changes: number; points: number }[]
  manual_admins: { admin: string; changes: number; points: number }[]
  suspicious_attendance: { member: string; event: string; checked_in_at: string; method: string }[]
  manual_checkins: { admin: string; count: number }[]
  big_reading_days: { member: string; day: string; pages: number }[]
  repeated_receipts: { member: string; amount_uzs: number; status: string; created_at: string; group: string }[]
  thresholds: { fast_share: number; high_share: number; manual_per_member: number; manual_per_admin: number; manual_checkins_per_admin: number; pages_a_day: number }
}

interface CertificateCheck {
  code: string
  member: string
  title: string
  place: number | null
  issued_at: string
  valid: boolean
  revoked_at: string | null
  revoke_reason: string | null
}

function Section({ title, hint, count, children }: { title: string; hint: string; count: number; children: ReactNode }) {
  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        <Badge tone={count ? 'warning' : 'success'}>{count ? `${count} ta` : 'toza'}</Badge>
      </div>
      <p className="text-sm text-app-hint">{hint}</p>
      {children}
    </Card>
  )
}

function CertificateLookup() {
  const { api } = useSession()
  const [code, setCode] = useState('')
  const [result, setResult] = useState<CertificateCheck | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function check() {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      setResult(await api<CertificateCheck>(`/api/v1/admin/trust/certificate?code=${encodeURIComponent(code.trim())}`))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Tekshirib bo‘lmadi.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-2 p-4">
      <h2 className="font-semibold">🎓 Sertifikatni tekshirish</h2>
      <p className="text-sm text-app-hint">Sertifikat ostidagi kodni kiriting (QR kod yonida yozilgan).</p>
      <div className="flex gap-2">
        <Input value={code} placeholder="Masalan: K7F2Q9XA" onChange={(event) => setCode(event.target.value)} />
        <Button loading={busy} disabled={code.trim().length < 4} onClick={() => void check()}>
          Tekshirish
        </Button>
      </div>
      <InlineError message={error} />
      {result && (
        <div className={`rounded-lg px-3 py-2 text-sm ${result.valid ? 'bg-emerald-50 text-emerald-900' : 'bg-red-50 text-red-900'}`}>
          <p className="font-semibold">{result.valid ? '✅ Haqiqiy sertifikat' : '⛔ Bekor qilingan sertifikat'}</p>
          <p>
            {result.member} — «{result.title}»{result.place ? `, ${result.place}-o‘rin` : ''}
          </p>
          <p>Berilgan: {formatDate(result.issued_at)}</p>
          {!result.valid && (
            <p>
              Bekor qilingan: {formatDate(result.revoked_at)}
              {result.revoke_reason ? ` — ${result.revoke_reason}` : ''}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

/** «🛡 Ishonch markazi»: unusual numbers to look at again — a list to check, not an accusation. */
export function TrustPage() {
  const { api } = useSession()
  const [days, setDays] = useState(30)
  const { state, reload } = useAsync((signal) => api<Trust>(`/api/v1/admin/trust?days=${days}`, { signal }), [days])

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="🛡 Ishonch markazi"
        subtitle="G‘ayrioddiy holatlar ro‘yxati: bu ayblov emas — qo‘shimcha tekshirish uchun. Ism ustida ishlang: a’zo bilan gaplashing, chekni bankda ko‘ring."
        actions={
          <Select value={days} onChange={(event) => setDays(Number(event.target.value))}>
            <option value={7}>Oxirgi 7 kun</option>
            <option value={30}>Oxirgi 30 kun</option>
            <option value={90}>Oxirgi 90 kun</option>
          </Select>
        }
      />
      <CertificateLookup />
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <>
          <Section
            title="⚡ Juda tez va juda yuqori test natijalari"
            hint={`Ajratilgan vaqtning ${Math.round(state.data.thresholds.fast_share * 100)}% idan kam vaqtda ${Math.round(state.data.thresholds.high_share * 100)}%+ ball olinganlar.`}
            count={state.data.fast_tests.length}
          >
            <Table head={['A’zo', 'Test', 'Ball', 'Vaqt', 'Qachon']}>
              {state.data.fast_tests.length === 0 && <EmptyRow colSpan={5} text="Hech narsa topilmadi" />}
              {state.data.fast_tests.map((row, index) => (
                <tr key={index}>
                  <td className="px-4 py-2">{row.member}</td>
                  <td className="px-4 py-2">{row.test}</td>
                  <td className="px-4 py-2 tabular-nums">
                    {row.score}/{row.max_score}
                  </td>
                  <td className="px-4 py-2 tabular-nums">
                    {Math.floor(row.seconds / 60)} daq {row.seconds % 60} s / {row.allowed_minutes} daq
                  </td>
                  <td className="px-4 py-2">{formatDateTime(row.submitted_at)}</td>
                </tr>
              ))}
            </Table>
          </Section>

          <Section
            title="✍️ Qo‘lda ko‘p o‘zgartirilgan ballar"
            hint={`A’zoga ${state.data.thresholds.manual_per_member}+ marta yoki bitta admin tomonidan ${state.data.thresholds.manual_per_admin}+ marta qo‘lda ball qo‘shilgan/ayirilgan.`}
            count={state.data.manual_members.length + state.data.manual_admins.length}
          >
            <Table head={['Kim', 'Turi', 'O‘zgarishlar', 'Jami ball']}>
              {state.data.manual_members.length + state.data.manual_admins.length === 0 && <EmptyRow colSpan={4} text="Hech narsa topilmadi" />}
              {state.data.manual_members.map((row) => (
                <tr key={`m-${row.member}`}>
                  <td className="px-4 py-2">{row.member}</td>
                  <td className="px-4 py-2">a’zo</td>
                  <td className="px-4 py-2 tabular-nums">{row.changes}</td>
                  <td className="px-4 py-2 tabular-nums">{row.points}</td>
                </tr>
              ))}
              {state.data.manual_admins.map((row) => (
                <tr key={`a-${row.admin}`}>
                  <td className="px-4 py-2">{row.admin}</td>
                  <td className="px-4 py-2">admin</td>
                  <td className="px-4 py-2 tabular-nums">{row.changes}</td>
                  <td className="px-4 py-2 tabular-nums">{row.points}</td>
                </tr>
              ))}
            </Table>
          </Section>

          <Section
            title="📍 Davomat"
            hint={`Shubhali deb belgilangan davomatlar va bitta admin qo‘lda ${state.data.thresholds.manual_checkins_per_admin}+ marta tasdiqlagan holatlar.`}
            count={state.data.suspicious_attendance.length + state.data.manual_checkins.length}
          >
            <Table head={['A’zo / admin', 'Tadbir', 'Qachon / soni']}>
              {state.data.suspicious_attendance.length + state.data.manual_checkins.length === 0 && <EmptyRow colSpan={3} text="Hech narsa topilmadi" />}
              {state.data.suspicious_attendance.map((row, index) => (
                <tr key={`s-${index}`}>
                  <td className="px-4 py-2">{row.member}</td>
                  <td className="px-4 py-2">{row.event}</td>
                  <td className="px-4 py-2">{formatDateTime(row.checked_in_at)}</td>
                </tr>
              ))}
              {state.data.manual_checkins.map((row) => (
                <tr key={`c-${row.admin}`}>
                  <td className="px-4 py-2">{row.admin} (admin)</td>
                  <td className="px-4 py-2">qo‘lda tasdiqlagan</td>
                  <td className="px-4 py-2 tabular-nums">{row.count} ta</td>
                </tr>
              ))}
            </Table>
          </Section>

          <Section
            title="📖 Kundalikdagi juda katta raqamlar"
            hint={`Bir kunda ${state.data.thresholds.pages_a_day}+ bet yozilgan kunlar (kunlik chegara Sozlamalarda).`}
            count={state.data.big_reading_days.length}
          >
            <Table head={['A’zo', 'Kun', 'Bet']}>
              {state.data.big_reading_days.length === 0 && <EmptyRow colSpan={3} text="Hech narsa topilmadi" />}
              {state.data.big_reading_days.map((row, index) => (
                <tr key={index}>
                  <td className="px-4 py-2">{row.member}</td>
                  <td className="px-4 py-2">{formatDate(row.day)}</td>
                  <td className="px-4 py-2 tabular-nums">{row.pages}</td>
                </tr>
              ))}
            </Table>
          </Section>

          <Section title="🧾 Takroriy cheklar" hint="Aynan bir xil chek fayli bir necha marta yuborilgan to‘lovlar (guruh — bir xil chek)." count={state.data.repeated_receipts.length}>
            <Table head={['A’zo', 'Summa', 'Holat', 'Qachon', 'Guruh']}>
              {state.data.repeated_receipts.length === 0 && <EmptyRow colSpan={5} text="Hech narsa topilmadi" />}
              {state.data.repeated_receipts.map((row, index) => (
                <tr key={index}>
                  <td className="px-4 py-2">{row.member}</td>
                  <td className="px-4 py-2 tabular-nums">{row.amount_uzs.toLocaleString('ru-RU')} so‘m</td>
                  <td className="px-4 py-2">{row.status}</td>
                  <td className="px-4 py-2">{formatDateTime(row.created_at)}</td>
                  <td className="px-4 py-2 font-mono text-xs">{row.group}</td>
                </tr>
              ))}
            </Table>
          </Section>
        </>
      )}
    </div>
  )
}
