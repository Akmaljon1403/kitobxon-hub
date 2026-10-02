import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import {
  Badge,
  Button,
  Card,
  EmptyRow,
  Field,
  InlineError,
  Input,
  Modal,
  PageHeader,
  Pagination,
  Select,
  Table,
  Textarea,
} from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminUser, Page } from '../types/api'
import { formatDateTime } from '../utils/format'
import { MemberPicker } from './ScoresPage'

type Kind = 'TEST_PLACE' | 'MONTHLY_TOP' | 'MANUAL'

interface AdminCertificate {
  id: string
  kind: Kind
  place: number | null
  title: string
  description: string
  issued_at: string
  code: string
  member: { user_id: string; first_name: string; last_name: string; member_number: string }
  revoked_at: string | null
  revoke_reason: string | null
}

const KINDS: Record<Kind, string> = {
  TEST_PLACE: 'Test g‘olibi',
  MONTHLY_TOP: 'Oy yetakchisi',
  MANUAL: "Qo'lda berilgan",
}
const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }
const LIMIT = 30

function IssueModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { api } = useSession()
  const [member, setMember] = useState<AdminUser | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [place, setPlace] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      await api('/api/v1/admin/certificates', {
        method: 'POST',
        body: {
          user_id: member?.id,
          title: title.trim(),
          description: description.trim(),
          place: place ? Number(place) : null,
        },
      })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Sertifikat berish" onClose={onClose}>
      <Field label="A'zo">
        <MemberPicker value={member} onChange={setMember} />
      </Field>
      <Field label="Sertifikat nomi" hint="Ro'yxatlarda ko'rinadi. Masalan: «Faol kitobxon», «Eng yaxshi taqriz»">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} placeholder="Faol kitobxon" />
      </Field>
      <Field label="Matn (ismdan keyin yoziladi)" hint="Masalan: «Klub faoliyatida faol ishtirok etgani uchun taqdim etiladi.»">
        <Textarea
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={400}
          placeholder="... uchun taqdim etiladi."
        />
      </Field>
      <Field label="O'rin (ixtiyoriy)" hint="Tanlansa, sertifikatda oltin/kumush/bronza medal chiziladi">
        <Select value={place} onChange={(e) => setPlace(e.target.value)}>
          <option value="">O'rinsiz</option>
          <option value="1">🥇 1-o'rin</option>
          <option value="2">🥈 2-o'rin</option>
          <option value="3">🥉 3-o'rin</option>
        </Select>
      </Field>
      <InlineError message={error} />
      <p className="text-xs text-app-hint">Sertifikat PDF ko'rinishida bot orqali a'zoga darhol yuboriladi.</p>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Bekor qilish
        </Button>
        <Button
          loading={busy}
          disabled={!member || title.trim().length < 3 || description.trim().length < 10}
          onClick={() => void submit()}
        >
          Berish
        </Button>
      </div>
    </Modal>
  )
}

export function CertificatesPage() {
  const { api, download } = useSession()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<'' | Kind>('')
  const [offset, setOffset] = useState(0)
  const [issuing, setIssuing] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const params = new URLSearchParams({ limit: String(LIMIT), offset: String(offset) })
  if (query) params.set('q', query)
  if (kind) params.set('kind', kind)
  const { state, reload } = useAsync(
    (signal) => api<Page<AdminCertificate>>(`/api/v1/admin/certificates?${params}`, { signal }),
    [query, kind, offset],
  )

  async function savePdf(certificate: AdminCertificate) {
    setError(null)
    try {
      const blob = await download(`/api/v1/admin/certificates/${certificate.id}/pdf`)
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `sertifikat-${certificate.code}.pdf`
      link.click()
      URL.revokeObjectURL(link.href)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "PDFni yuklab bo'lmadi.")
    }
  }

  async function revoke(certificate: AdminCertificate) {
    const reason = window.prompt(`«${certificate.title}» sertifikatini bekor qilish sababi:`)
    if (!reason) return
    setError(null)
    try {
      await api(`/api/v1/admin/certificates/${certificate.id}/revoke`, { method: 'POST', body: { reason } })
      setMessage('Sertifikat bekor qilindi. QR kod endi «Bekor qilingan» deb ko‘rsatadi.')
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    }
  }

  return (
    <>
      <PageHeader
        title="Sertifikatlar"
        subtitle="Test g'oliblari (1–3-o'rin) va oy yakunidagi reyting yetakchilari sertifikatni avtomatik oladi. Bu yerda qo'lda ham berish mumkin."
        actions={<Button onClick={() => setIssuing(true)}>➕ Sertifikat berish</Button>}
      />
      <div className="flex flex-wrap gap-2">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            setOffset(0)
            setQuery(search.trim())
          }}
        >
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Ism, nom yoki kod" aria-label="Qidirish" />
          <Button variant="secondary" type="submit">
            Qidirish
          </Button>
        </form>
        <div className="w-48">
          <Select
            value={kind}
            onChange={(e) => {
              setOffset(0)
              setKind(e.target.value as '' | Kind)
            }}
            aria-label="Turi"
          >
            <option value="">Barcha turlar</option>
            {(Object.keys(KINDS) as Kind[]).map((value) => (
              <option key={value} value={value}>
                {KINDS[value]}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <InlineError message={error} />
      {message && <p className="text-sm text-emerald-600">{message}</p>}
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <Card>
          <Table head={["A'zo", 'Sertifikat', 'Turi', 'Berilgan', '']}>
            {state.data.items.length === 0 && <EmptyRow colSpan={5} text="Hozircha sertifikat berilmagan" />}
            {state.data.items.map((certificate) => (
              <tr key={certificate.id} className={certificate.revoked_at ? 'opacity-60' : ''}>
                <td className="px-4 py-2">
                  {certificate.member.last_name} {certificate.member.first_name}
                  <p className="font-mono text-xs text-app-hint">{certificate.member.member_number}</p>
                </td>
                <td className="px-4 py-2">
                  <span className="mr-1">{(certificate.place && MEDALS[certificate.place]) || '🎓'}</span>
                  {certificate.title}
                  <p className="font-mono text-xs text-app-hint">{certificate.code}</p>
                  {certificate.revoked_at && (
                    <p className="text-xs text-app-danger">Bekor qilingan: {certificate.revoke_reason}</p>
                  )}
                </td>
                <td className="px-4 py-2">
                  <Badge tone={certificate.kind === 'MANUAL' ? 'neutral' : 'info'}>{KINDS[certificate.kind]}</Badge>
                </td>
                <td className="whitespace-nowrap px-4 py-2 text-sm">{formatDateTime(certificate.issued_at)}</td>
                <td className="whitespace-nowrap px-4 py-2 text-right">
                  <Button variant="ghost" onClick={() => void savePdf(certificate)}>
                    📄 PDF
                  </Button>
                  {!certificate.revoked_at && (
                    <Button variant="ghost" className="text-app-danger" onClick={() => void revoke(certificate)}>
                      Bekor qilish
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
          <Pagination total={state.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
        </Card>
      )}
      {issuing && (
        <IssueModal
          onClose={() => setIssuing(false)}
          onDone={() => {
            setIssuing(false)
            setMessage('✓ Sertifikat berildi va bot orqali a‘zoga yuborilmoqda.')
            reload()
          }}
        />
      )}
    </>
  )
}
