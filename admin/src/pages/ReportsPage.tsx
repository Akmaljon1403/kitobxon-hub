import { useEffect, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, Field, InlineError, Input, Modal, PageHeader, Select, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError, saveBlob } from '../services/api'
import { useSession } from '../store/session'
import type { AdminEvent, Page, ReportDetail, ReportKind, ReportListItem, ReportStatus } from '../types/api'
import { formatDateTime } from '../utils/format'
import { navigate } from '../utils/router'

const STATUS: Record<ReportStatus, { label: string; tone: 'neutral' | 'info' | 'warning' | 'success' }> = {
  DRAFT: { label: 'Qoralama', tone: 'neutral' },
  AI_GENERATED: { label: 'AI qoralamasi', tone: 'info' },
  REVIEW: { label: "Ko'rib chiqilmoqda", tone: 'warning' },
  APPROVED: { label: 'Tasdiqlangan', tone: 'success' },
  PDF_GENERATED: { label: 'PDF tayyor', tone: 'success' },
  ARCHIVED: { label: 'Arxivda', tone: 'neutral' },
}

function StatusBadge({ status }: { status: ReportStatus }) {
  return <Badge tone={STATUS[status].tone}>{STATUS[status].label}</Badge>
}

const KINDS: { kind: ReportKind; icon: string; title: string; hint: string }[] = [
  { kind: 'EVENT', icon: '📅', title: 'Tadbir hisoboti', hint: "Bitta tadbir: davomat, fakultetlar, test natijalari, baholar" },
  { kind: 'PERIOD', icon: '🗓', title: 'Davr hisoboti', hint: "Oy yoki chorak: barcha tadbirlar, yangi a'zolar, eng faollar" },
  { kind: 'GENERAL', icon: '📝', title: 'Umumiy hisobot', hint: "Istalgan mavzu: o'z matningiz va rasmlar asosida" },
]

function isoDate(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
}

function NewReportModal({ onClose }: { onClose: () => void }) {
  const { api } = useSession()
  const events = useAsync((signal) => api<Page<AdminEvent>>('/api/v1/admin/events?limit=200', { signal }))
  const today = new Date()
  const [kind, setKind] = useState<ReportKind>('EVENT')
  const [eventId, setEventId] = useState('')
  const [start, setStart] = useState(isoDate(new Date(today.getFullYear(), today.getMonth(), 1)))
  const [end, setEnd] = useState(isoDate(today))
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ready = kind === 'EVENT' ? Boolean(eventId) : kind === 'PERIOD' ? Boolean(start && end) : title.trim().length >= 3

  async function create() {
    setBusy(true)
    setError(null)
    const body =
      kind === 'EVENT'
        ? { kind, event_id: eventId }
        : kind === 'PERIOD'
          ? { kind, period_start: start, period_end: end }
          : { kind, title: title.trim() }
    try {
      const report = await api<ReportDetail>('/api/v1/admin/reports', { method: 'POST', body })
      navigate(`/reports/${report.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yaratib bo'lmadi.")
      setBusy(false)
    }
  }

  function lastMonth() {
    setStart(isoDate(new Date(today.getFullYear(), today.getMonth() - 1, 1)))
    setEnd(isoDate(new Date(today.getFullYear(), today.getMonth(), 0)))
  }

  return (
    <Modal
      title="Yangi hisobot"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Bekor qilish
          </Button>
          <Button loading={busy} disabled={!ready} onClick={() => void create()}>
            Yaratish
          </Button>
        </>
      }
    >
      <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Hisobot turi">
        {KINDS.map((item) => (
          <button
            key={item.kind}
            type="button"
            role="radio"
            aria-checked={kind === item.kind}
            onClick={() => setKind(item.kind)}
            className={`flex flex-col gap-1 rounded-xl border p-3 text-left ${kind === item.kind ? 'border-app-button bg-app-button/10' : 'border-app-border'}`}
          >
            <span className="text-2xl">{item.icon}</span>
            <span className="text-sm font-semibold">{item.title}</span>
            <span className="text-xs text-app-hint">{item.hint}</span>
          </button>
        ))}
      </div>
      {kind === 'EVENT' && (
        <Field label="Tadbir" hint="Ro'yxatdan o'tganlar, davomat, test natijalari shu tadbirdan avtomatik olinadi">
          <Select value={eventId} onChange={(e) => setEventId(e.target.value)}>
            <option value="">— Tadbirni tanlang —</option>
            {events.state.status === 'success' &&
              events.state.data.items.map((event) => (
                <option key={event.id} value={event.id}>
                  {formatDateTime(event.starts_at)} — {event.title}
                </option>
              ))}
          </Select>
        </Field>
      )}
      {kind === 'PERIOD' && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Boshlanishi">
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
            <Field label="Tugashi">
              <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </Field>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => {
              setStart(isoDate(new Date(today.getFullYear(), today.getMonth(), 1)))
              setEnd(isoDate(today))
            }}>
              Shu oy
            </Button>
            <Button variant="secondary" onClick={lastMonth}>
              O'tgan oy
            </Button>
          </div>
        </>
      )}
      {kind === 'GENERAL' && (
        <Field label="Hisobot mavzusi" hint="Masalan: «Kutubxonaga kitob topshirish aksiyasi». Keyin matn yozasiz va rasmlar yuklaysiz.">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={255} placeholder="Hisobot mavzusi" />
        </Field>
      )}
      <InlineError message={error} />
    </Modal>
  )
}

export function ReportsPage() {
  const { api, can } = useSession()
  const [creating, setCreating] = useState(false)
  const { state, reload } = useAsync((signal) => api<Page<ReportListItem>>('/api/v1/admin/reports?limit=200', { signal }))

  return (
    <>
      <PageHeader
        title="Hisobotlar"
        subtitle="Rasmiy PDF hisobot: tadbir, davr (masalan, oylik) yoki istalgan mavzu bo'yicha, rasmlar bilan. Raqamlar bazadan olinadi; matnni AI yoki shablon tayyorlaydi, admin tekshirib tasdiqlaydi."
        actions={can('REPORT_CREATE') && <Button onClick={() => setCreating(true)}>+ Yangi hisobot</Button>}
      />
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={['Hisobot', 'Mavzu', 'Holat', 'Yaratilgan', '']}>
            {state.data.items.length === 0 && <EmptyRow colSpan={5} text="Hisobotlar hali yo'q" />}
            {state.data.items.map((report) => (
              <tr key={report.id}>
                <td className="px-4 py-2.5">
                  <p className="font-medium">{report.title}</p>
                  <p className="text-xs text-app-hint">{report.version}-versiya</p>
                </td>
                <td className="px-4 py-2.5 text-sm">{report.event_title}</td>
                <td className="px-4 py-2.5">
                  <StatusBadge status={report.status} />
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm">{formatDateTime(report.created_at)}</td>
                <td className="px-4 py-2.5 text-right">
                  <Button variant="ghost" onClick={() => navigate(`/reports/${report.id}`)}>
                    Ochish
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {creating && <NewReportModal onClose={() => setCreating(false)} />}
    </>
  )
}

const FIELDS: { key: keyof ReportDetail; label: string; hint?: string; rows: number }[] = [
  { key: 'objective', label: 'Maqsad', rows: 2 },
  { key: 'activity_description', label: 'Tadbir qanday o\'tdi', hint: "O'z so'zlaringiz bilan qisqacha yozing — AI uni rasmiy uslubga keltiradi", rows: 4 },
  { key: 'results', label: 'Natijalar', rows: 2 },
  { key: 'conclusion', label: 'Xulosa', rows: 2 },
  { key: 'recommendations', label: 'Takliflar', rows: 2 },
]

function Photo({ reportId, photo, canEdit, onDeleted }: { reportId: string; photo: ReportDetail['photos'][number]; canEdit: boolean; onDeleted: () => void }) {
  const { api, download } = useSession()
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let url: string | null = null
    download(`/api/v1/admin/reports/${reportId}/photos/${photo.id}`)
      .then((blob) => {
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => setSrc(null))
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [download, reportId, photo.id])
  return (
    <figure className="flex flex-col gap-1">
      <div className="aspect-[4/3] overflow-hidden rounded-lg bg-app-surface">{src && <img src={src} alt={photo.caption ?? ''} className="size-full object-cover" />}</div>
      <figcaption className="flex items-center justify-between gap-2 text-xs text-app-hint">
        <span className="truncate">{photo.caption ?? '—'}</span>
        {canEdit && (
          <button
            type="button"
            className="text-app-danger"
            onClick={() => {
              if (window.confirm("Rasmni o'chirasizmi?"))
                void api(`/api/v1/admin/reports/${reportId}/photos/${photo.id}`, { method: 'DELETE' }).then(onDeleted)
            }}
          >
            O'chirish
          </button>
        )}
      </figcaption>
    </figure>
  )
}

export function ReportEditorPage({ reportId }: { reportId: string }) {
  const { api, can, download } = useSession()
  const { state, reload } = useAsync((signal) => api<ReportDetail>(`/api/v1/admin/reports/${reportId}`, { signal }), [reportId])
  const [form, setForm] = useState<Record<string, string>>({})
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)
  const [caption, setCaption] = useState('')
  // Unsaved typing must survive reloads (e.g. after a photo upload).
  const [formDirty, setFormDirty] = useState(false)
  const [bodyDirty, setBodyDirty] = useState(false)

  useEffect(() => {
    if (state.status !== 'success') return
    const report = state.data
    if (!formDirty)
      setForm({
        title: report.title,
        objective: report.objective ?? '',
        activity_description: report.activity_description ?? '',
        results: report.results ?? '',
        conclusion: report.conclusion ?? '',
        recommendations: report.recommendations ?? '',
      })
    if (!bodyDirty) setBody(report.body_text ?? '')
    // Only server responses refresh the editors; dirty flags are read at that moment.
  }, [state])

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const report = state.data
  const editable = ['DRAFT', 'AI_GENERATED', 'REVIEW'].includes(report.status) && can('REPORT_CREATE')
  const facts = report.facts

  async function run(label: string, action: () => Promise<unknown>, done?: string) {
    setBusy(label)
    setError(null)
    setSaved(null)
    try {
      await action()
      if (done) setSaved(done)
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(null)
    }
  }

  async function downloadPdf(path: string, name: string) {
    await run('pdf', async () => saveBlob(await download(path), name))
  }

  async function upload(file: File) {
    const data = new FormData()
    data.append('file', file)
    if (caption.trim()) data.append('caption', caption.trim())
    await run('photo', () => api(`/api/v1/admin/reports/${report.id}/photos`, { method: 'POST', body: data }), "✓ Rasm qo'shildi")
    setCaption('')
  }

  return (
    <>
      <PageHeader
        title={report.title}
        subtitle={`${facts.event?.title ?? facts.period?.label ?? 'Umumiy hisobot'} · ${report.version}-versiya`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={report.status} />
            <Button variant="secondary" onClick={() => navigate('/reports')}>
              ← Hisobotlar
            </Button>
            <Button variant="secondary" loading={busy === 'pdf'} onClick={() => void downloadPdf(`/api/v1/admin/reports/${report.id}/preview.pdf`, 'hisobot_qoralama.pdf')}>
              👁 Ko'rib chiqish (PDF)
            </Button>
            {report.pdf_ready && (
              <Button onClick={() => void downloadPdf(`/api/v1/admin/reports/${report.id}/pdf`, `hisobot_v${report.version}.pdf`)}>⬇ Rasmiy PDF</Button>
            )}
            {can('REPORT_APPROVE') && ['AI_GENERATED', 'REVIEW'].includes(report.status) && (
              <Button
                loading={busy === 'approve'}
                disabled={report.number_issues.length > 0}
                title={report.number_issues.length ? 'Avval matndagi tekshirilmagan raqamlarni tuzating' : undefined}
                onClick={() => {
                  if (window.confirm("Hisobotni tasdiqlaysizmi? Tasdiqlangandan so'ng matnni o'zgartirib bo'lmaydi (faqat yangi versiya)."))
                    void run('approve', () => api(`/api/v1/admin/reports/${report.id}/approve`, { method: 'POST' }), '✓ Tasdiqlandi, rasmiy PDF tayyor')
                }}
              >
                ✓ Tasdiqlash va PDF
              </Button>
            )}
            {can('REPORT_CREATE') && ['APPROVED', 'PDF_GENERATED', 'ARCHIVED'].includes(report.status) && (
              <Button
                variant="secondary"
                onClick={() =>
                  void run('version', async () => {
                    const next = await api<ReportDetail>(`/api/v1/admin/reports/${report.id}/new-version`, { method: 'POST' })
                    navigate(`/reports/${next.id}`)
                  })
                }
              >
                Yangi versiya
              </Button>
            )}
            {can('REPORT_APPROVE') && report.status === 'PDF_GENERATED' && (
              <Button variant="ghost" onClick={() => void run('archive', () => api(`/api/v1/admin/reports/${report.id}/archive`, { method: 'POST' }))}>
                Arxivlash
              </Button>
            )}
          </div>
        }
      />
      <InlineError message={error} />
      {saved && <p className="text-sm text-emerald-600">{saved}</p>}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card className="flex flex-col gap-3 p-4">
            <h2 className="font-semibold">1. Sizning ma'lumotlaringiz</h2>
            <Field label="Hisobot nomi">
              <Input
                value={form.title ?? ''}
                onChange={(e) => {
                  setFormDirty(true)
                  setForm({ ...form, title: e.target.value })
                }} disabled={!editable} maxLength={255} />
            </Field>
            {FIELDS.map((field) => (
              <Field
                key={field.key}
                label={field.key === 'activity_description' && report.kind !== 'EVENT' ? 'Amalga oshirilgan ishlar' : field.label}
                hint={field.hint}
              >
                <Textarea
                  rows={field.rows}
                  value={form[field.key] ?? ''}
                  onChange={(e) => {
                    setFormDirty(true)
                    setForm({ ...form, [field.key]: e.target.value })
                  }}
                  disabled={!editable}
                />
              </Field>
            ))}
            {editable && (
              <div className="flex justify-end">
                <Button
                  loading={busy === 'fields'}
                  onClick={() =>
                    void run('fields', async () => {
                      await api(`/api/v1/admin/reports/${report.id}`, { method: 'PATCH', body: form })
                      setFormDirty(false)
                    }, '✓ Saqlandi')
                  }
                >
                  Saqlash
                </Button>
              </div>
            )}
          </Card>

          <Card className="flex flex-col gap-3 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">2. Hisobot matni</h2>
              {editable && (
                <div className="flex flex-wrap gap-2">
                  {report.ai_available && (
                    <Button
                      loading={busy === 'ai'}
                      onClick={() =>
                        void run('ai', async () => {
                          await api(`/api/v1/admin/reports/${report.id}`, { method: 'PATCH', body: form })
                          await api(`/api/v1/admin/reports/${report.id}/generate`, { method: 'POST', body: { use_ai: true } })
                          setFormDirty(false)
                          setBodyDirty(false)
                        }, '✓ AI qoralama tayyor — tekshirib chiqing')
                      }
                    >
                      🤖 AI bilan yozish
                    </Button>
                  )}
                  <Button
                    variant="secondary"
                    loading={busy === 'template'}
                    onClick={() =>
                      void run('template', async () => {
                        await api(`/api/v1/admin/reports/${report.id}`, { method: 'PATCH', body: form })
                        await api(`/api/v1/admin/reports/${report.id}/generate`, { method: 'POST', body: { use_ai: false } })
                        setFormDirty(false)
                        setBodyDirty(false)
                      }, '✓ Shablon bo\'yicha qoralama tayyor')
                    }
                  >
                    📄 Shablon bo'yicha
                  </Button>
                </div>
              )}
            </div>
            {!report.ai_available && editable && (
              <p className="text-xs text-app-hint">AI yordamchi ulanmagan (AI_API_KEY). Shablon bo'yicha qoralama ham rasmiy uslubda tayyorlanadi.</p>
            )}
            {report.ai_generated_at && (
              <p className="text-xs text-app-hint">
                AI ({report.ai_model}) tomonidan {formatDateTime(report.ai_generated_at)} da yozilgan. Har bir jumlani tekshiring.
              </p>
            )}
            {report.number_issues.length > 0 && (
              <div role="alert" className="rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
                ⚠️ Matnda bazada yo'q raqamlar bor: <b>{report.number_issues.join(', ')}</b>. Ularni o'chiring yoki to'g'riligiga ishonchingiz komil bo'lsa, «Natijalar» kabi maydonga yozing.
              </div>
            )}
            <Textarea
              rows={18}
              value={body}
              onChange={(e) => {
                setBodyDirty(true)
                setBody(e.target.value)
              }}
              disabled={!editable}
              placeholder="Qoralama tayyorlash uchun yuqoridagi tugmalardan birini bosing yoki o'zingiz yozing. Sarlavhalarni «## » bilan boshlang."
              className="font-mono text-sm"
            />
            {editable && (
              <div className="flex justify-end">
                <Button
                  loading={busy === 'body'}
                  disabled={!bodyDirty}
                  onClick={() =>
                    void run('body', async () => {
                      await api(`/api/v1/admin/reports/${report.id}`, { method: 'PATCH', body: { body_text: body } })
                      setBodyDirty(false)
                    }, '✓ Matn saqlandi')
                  }
                >
                  Matnni saqlash
                </Button>
              </div>
            )}
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card className="flex flex-col gap-2 p-4 text-sm">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold">Bazadagi faktlar</h2>
              {editable && (
                <Button variant="ghost" loading={busy === 'facts'} onClick={() => void run('facts', () => api(`/api/v1/admin/reports/${report.id}/refresh-facts`, { method: 'POST' }), '✓ Faktlar yangilandi')}>
                  ↻ Yangilash
                </Button>
              )}
            </div>
            {report.kind === 'EVENT' && facts.event && (
              <>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              <dt className="text-app-hint">Sana</dt>
              <dd>
                {facts.event?.date}, {facts.event?.time}
              </dd>
              <dt className="text-app-hint">Joy</dt>
              <dd>{facts.event?.location ?? '—'}</dd>
              <dt className="text-app-hint">Kitob</dt>
              <dd>{facts.event?.book_title ? `${facts.event?.book_author}. «${facts.event?.book_title}»` : '—'}</dd>
              <dt className="text-app-hint">Mas'ul</dt>
              <dd>{facts.event?.responsible ?? '—'}</dd>
            </dl>
            <div className="mt-1 grid grid-cols-2 gap-2">
              {[
                ["Ro'yxatdan o'tgan", facts.attendance?.registered],
                ['Qatnashdi', facts.attendance?.attended],
                ['Davomat', facts.attendance?.rate_percent != null ? `${facts.attendance?.rate_percent}%` : '—'],
                ["Ro'yxatsiz kelgan", facts.attendance?.walk_ins],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg bg-app-surface p-2">
                  <p className="text-xs text-app-hint">{label}</p>
                  <p className="text-lg font-semibold tabular-nums">{value}</p>
                </div>
              ))}
            </div>
            {(facts.faculties ?? []).length > 0 && (
              <p className="text-xs text-app-hint">{(facts.faculties ?? []).map((row) => `${row.name}: ${row.attended}`).join(' · ')}</p>
            )}
            {(facts.tests ?? []).map((test) => (
              <p key={test.title} className="text-xs text-app-hint">
                📝 {test.title}: {test.participants} ishtirokchi, o'rtacha {test.average_score}/{test.max_score}
              </p>
            ))}
              </>
            )}
            {report.kind === 'PERIOD' && facts.summary && (
              <>
                <p className="font-medium">{facts.period?.label}</p>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    ['Tadbirlar', facts.summary.events],
                    ['Qatnashuvlar', facts.summary.attendances],
                    ["Turli a'zolar", facts.summary.participants],
                    ["Yangi a'zolar", facts.summary.new_members],
                    ["O'qilgan kitoblar", facts.summary.books_completed],
                    ['Sertifikatlar', facts.summary.certificates],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg bg-app-surface p-2">
                      <p className="text-xs text-app-hint">{label}</p>
                      <p className="text-lg font-semibold tabular-nums">{value}</p>
                    </div>
                  ))}
                </div>
                {(facts.top_members ?? []).length > 0 && (
                  <p className="text-xs text-app-hint">
                    🏆 {(facts.top_members ?? []).map((row) => `${row.place}. ${row.name} (${row.points})`).join(' · ')}
                  </p>
                )}
              </>
            )}
            {report.kind === 'GENERAL' && (
              <p className="text-app-hint">Umumiy hisobot sizning matningiz va rasmlaringizdan tuziladi — bazadan raqam olinmaydi.</p>
            )}
            {facts.feedback && facts.feedback.count > 0 && (
              <p className="text-xs text-app-hint">
                ⭐ Ishtirokchilar bahosi: {facts.feedback.average} / 5 ({facts.feedback.count} ta baho)
              </p>
            )}
            <p className="text-xs text-app-hint">Holat: {formatDateTime(facts.prepared_at)}. Bu raqamlarni AI o'zgartira olmaydi.</p>
          </Card>

          <Card className="flex flex-col gap-3 p-4">
            <h2 className="font-semibold">Fotosuratlar ({report.photos.length}/8)</h2>
            {editable && report.photos.length < 8 && (
              <div className="flex flex-col gap-2">
                <Input value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Rasm izohi (ixtiyoriy)" maxLength={255} />
                <label className="inline-flex cursor-pointer items-center justify-center rounded-lg border border-dashed border-app-border px-3 py-3 text-sm text-app-link hover:bg-app-surface">
                  {busy === 'photo' ? 'Yuklanmoqda…' : '📷 Rasm tanlash (JPG/PNG, 8 MB gacha)'}
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) void upload(file)
                      e.target.value = ''
                    }}
                  />
                </label>
              </div>
            )}
            <div className="grid grid-cols-2 gap-2">
              {report.photos.map((photo) => (
                <Photo key={photo.id} reportId={report.id} photo={photo} canEdit={editable} onDeleted={reload} />
              ))}
            </div>
            {report.photos.length === 0 && <p className="text-sm text-app-hint">Rasm qo'shilmagan.</p>}
          </Card>
          {report.approved_by && (
            <Card className="p-4 text-sm">
              ✓ Tasdiqladi: <b>{report.approved_by}</b>, {formatDateTime(report.approved_at)}
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
