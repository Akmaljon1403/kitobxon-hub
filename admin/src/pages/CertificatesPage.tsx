import { useEffect, useState } from 'react'

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
  SectionTabs,
  Select,
  Table,
  Textarea,
} from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminUser, Page } from '../types/api'
import { formatDateTime } from '../utils/format'
import { navigate, useRoute } from '../utils/router'
import { MemberPicker } from './ScoresPage'

type Kind = 'TEST_PLACE' | 'MONTHLY_TOP' | 'MANUAL' | 'COMPLETION'

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
  design: string | null
}

interface Template {
  id: string
  name: string
  has_background: boolean
  bg_width: number
  bg_height: number
  is_default: boolean
}

const KINDS: Record<Kind, string> = {
  TEST_PLACE: 'Test g‘olibi',
  MONTHLY_TOP: 'Oy yetakchisi',
  MANUAL: "Qo'lda berilgan",
  COMPLETION: 'Ishtirok (test)',
}
const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }
const LIMIT = 30

function IssueModal({ onClose, onDone }: { onClose: () => void; onDone: (gift: boolean) => void }) {
  const { api } = useSession()
  const templates = useAsync((signal) => api<Template[]>('/api/v1/admin/certificate-templates', { signal }), [])
  const [member, setMember] = useState<AdminUser | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [place, setPlace] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [message, setMessage] = useState('')
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
          template_id: templateId || null,
          message: message.trim() || null,
        },
      })
      onDone(Boolean(message.trim()))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(false)
    }
  }

  const designs = templates.state.status === 'success' ? templates.state.data : []

  return (
    <Modal title="Sertifikat berish / sovg'a qilish" onClose={onClose}>
      <Field label="A'zo">
        <MemberPicker value={member} onChange={setMember} />
      </Field>
      <Field label="Dizayn (shablon)" hint="Bo'sh — klubning navbatdagi standart dizayni ishlatiladi">
        <Select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
          <option value="">Standart dizayn</option>
          {designs.map((design) => (
            <option key={design.id} value={design.id}>
              {design.name}
              {design.is_default ? ' (asosiy)' : ''}
            </option>
          ))}
        </Select>
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
      <Field
        label="Shaxsiy xabar (sovg'a uchun, ixtiyoriy)"
        hint="Yozsangiz — sertifikat PDF shu xabar bilan birga sovg'a sifatida botda yuboriladi"
      >
        <Textarea
          rows={2}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          maxLength={1000}
          placeholder="Tabriklaymiz! Mana sizga maxsus sertifikat 🎁"
        />
      </Field>
      <InlineError message={error} />
      <p className="text-xs text-app-hint">
        {message.trim()
          ? 'Sertifikat shaxsiy xabar bilan birga bot orqali darhol yuboriladi.'
          : "Sertifikat beriladi; a'zo uni ilovada ko'radi va yuklab oladi."}
      </p>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Bekor qilish
        </Button>
        <Button
          loading={busy}
          disabled={!member || title.trim().length < 3 || description.trim().length < 10}
          onClick={() => void submit()}
        >
          {message.trim() ? 'Sovg‘a qilish' : 'Berish'}
        </Button>
      </div>
    </Modal>
  )
}

/** The uploaded design picture as a card thumbnail (light; no server render). */
function TemplateThumb({ template }: { template: Template }) {
  const { download } = useSession()
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!template.has_background) return
    let revoke: string | null = null
    void download(`/api/v1/admin/certificate-templates/${template.id}/background`)
      .then((blob) => {
        revoke = URL.createObjectURL(blob)
        setUrl(revoke)
      })
      .catch(() => setUrl(null))
    return () => {
      if (revoke) URL.revokeObjectURL(revoke)
    }
  }, [template.id, template.has_background, download])
  return (
    <div className="flex aspect-[1.4] w-full items-center justify-center overflow-hidden rounded bg-app-muted/40">
      {url ? (
        <img src={url} alt="" className="h-full w-full object-contain" />
      ) : (
        <span className="text-xs text-app-hint">Rasm yuklanmagan</span>
      )}
    </div>
  )
}

function DesignsTab() {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<Template[]>('/api/v1/admin/certificate-templates', { signal }), [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function create() {
    setBusy(true)
    setError(null)
    try {
      const template = await api<Template>('/api/v1/admin/certificate-templates', {
        method: 'POST',
        body: { name: 'Yangi dizayn', elements: [], is_default: false },
      })
      navigate(`certificates/${template.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
      setBusy(false)
    }
  }

  async function remove(template: Template) {
    if (!window.confirm(`«${template.name}» dizaynini o'chirasizmi?`)) return
    try {
      await api(`/api/v1/admin/certificate-templates/${template.id}`, { method: 'DELETE' })
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "O'chirib bo'lmadi.")
    }
  }

  return (
    <div className="space-y-3">
      <Card className="p-4 text-sm text-app-hint">
        O'z dizayningizni (PNG, JPG yoki PDF) yuklab, ism, QR kod, muhr, imzo, sana va boshqa elementlarni xohlagan joyingizga
        qo'ying — matn to'g'ridan-to'g'ri rasm ustiga yoziladi, hech qanday qo'shimcha parda qo'yilmaydi. «Asosiy» deb
        belgilangan dizayn test g'oliblari va oy yetakchilariga avtomatik beriladi.
      </Card>
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Dizaynlar</h2>
        <Button onClick={() => void create()} loading={busy}>
          ➕ Yangi dizayn
        </Button>
      </div>
      <InlineError message={error} />
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' &&
        (state.data.length === 0 ? (
          <Card className="p-6 text-center text-sm text-app-hint">Hali dizayn yaratilmagan.</Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {state.data.map((template) => (
              <Card key={template.id} className="space-y-2 p-3">
                <TemplateThumb template={template} />
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">{template.name}</span>
                  {template.is_default && <Badge tone="success">Asosiy</Badge>}
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" className="flex-1" onClick={() => navigate(`certificates/${template.id}`)}>
                    ✏️ Tahrirlash
                  </Button>
                  <Button variant="ghost" className="text-app-danger" onClick={() => void remove(template)}>
                    O'chirish
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        ))}
    </div>
  )
}

function IssuedTab() {
  const { download } = useSession()
  const { api } = useSession()
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-app-hint">
          Test g'oliblari (1–3-o'rin), test topshirganlar va oy yetakchilari sertifikatni avtomatik oladi. Bu yerda qo'lda
          berish yoki sovg'a qilish ham mumkin.
        </p>
        <Button onClick={() => setIssuing(true)}>➕ Sertifikat berish</Button>
      </div>
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
          onDone={(gift) => {
            setIssuing(false)
            setMessage(gift ? '🎁 Sovg‘a sertifikat yuborilmoqda.' : '✓ Sertifikat berildi va bot orqali a‘zoga yuborilmoqda.')
            reload()
          }}
        />
      )}
    </>
  )
}

export function CertificatesPage() {
  const route = useRoute()
  const tab = route.query.get('tab') === 'designs' ? 'designs' : 'issued'

  return (
    <>
      <PageHeader
        title="Sertifikatlar"
        subtitle="Dizaynlarni yarating, test va tadbirlarga biriktiring; sertifikatlarni avtomatik yoki sovg'a sifatida bering."
      />
      <SectionTabs
        tabs={[
          { key: 'issued', label: '🎓 Berilgan sertifikatlar' },
          { key: 'designs', label: '🎨 Dizaynlar (muharrir)' },
        ]}
        active={tab}
        onChange={(key) => navigate(key === 'designs' ? 'certificates?tab=designs' : 'certificates')}
      />
      {tab === 'designs' ? <DesignsTab /> : <IssuedTab />}
    </>
  )
}
