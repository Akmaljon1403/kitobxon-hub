import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, Field, InlineError, Input, PageHeader, Select } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminEvent, AdminTest, Faculty, Page } from '../types/api'
import { formatDate } from '../utils/format'

interface DocumentTemplate {
  code: string
  title: string
  description: string
  formats: string[]
  params: string[]
}

interface ReportRow {
  id: string
  title: string
  status: string
  created_at: string
}

const FORMAT_LABEL: Record<string, string> = { xlsx: '📊 Excel', pdf: '📕 PDF', docx: '📝 Word' }

/** 1 September – 31 August of the current study year (what the institute counts). */
function studyYear(): [string, string] {
  const today = new Date()
  const start = today.getMonth() >= 8 ? today.getFullYear() : today.getFullYear() - 1
  return [`${start}-09-01`, `${start + 1}-08-31`]
}

/** Inside Telegram a file cannot be saved from the panel: there the bot brings it. */
const insideTelegram = Boolean((window as unknown as { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp?.initData)

function TemplateCard({ template, faculties }: { template: DocumentTemplate; faculties: Faculty[] }) {
  const { api, download } = useSession()
  const [yearStart, yearEnd] = studyYear()
  const [values, setValues] = useState<Record<string, string>>({ date_from: yearStart, date_to: yearEnd })
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const needs = (param: string) => template.params.includes(param)
  const events = useAsync(
    (signal) => (needs('event') ? api<Page<AdminEvent>>('/api/v1/admin/events?limit=100', { signal }) : Promise.resolve(null)),
    [template.code],
  )
  const tests = useAsync(
    (signal) => (needs('test') ? api<Page<AdminTest>>('/api/v1/admin/tests?limit=100', { signal }) : Promise.resolve(null)),
    [template.code],
  )
  const reports = useAsync(
    (signal) => (needs('report') ? api<Page<ReportRow>>('/api/v1/admin/reports?limit=100', { signal }) : Promise.resolve(null)),
    [template.code],
  )
  const set = (key: string) => (event: { target: { value: string } }) => setValues({ ...values, [key]: event.target.value })

  function params(): Record<string, string> {
    const result: Record<string, string> = {}
    if (needs('period')) {
      result.date_from = values.date_from
      result.date_to = values.date_to
    }
    for (const [param, key] of [
      ['faculty', 'faculty_id'],
      ['course', 'course'],
      ['group', 'group_name'],
      ['event', 'event_id'],
      ['test', 'test_id'],
      ['report', 'report_id'],
    ] as const) {
      if (needs(param) && values[key]?.trim()) result[key] = values[key].trim()
    }
    return result
  }

  async function save(format: string) {
    setBusy(`get:${format}`)
    setError(null)
    setDone(null)
    try {
      const query = new URLSearchParams({ ...params(), format })
      const blob = await download(`/api/v1/admin/documents/${template.code}/file?${query}`)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${template.code}.${format}`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Tayyorlab bo'lmadi.")
    } finally {
      setBusy(null)
    }
  }

  async function send(format: string) {
    setBusy(`send:${format}`)
    setError(null)
    setDone(null)
    try {
      await api(`/api/v1/admin/documents/${template.code}/send`, { method: 'POST', body: { ...params(), format } })
      setDone('✓ Fayl bot chatingizga yuborildi.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi.")
    } finally {
      setBusy(null)
    }
  }

  const missing =
    (needs('event') && !values.event_id) || (needs('test') && !values.test_id) || (needs('report') && !values.report_id)

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div>
        <h2 className="font-semibold">{template.title}</h2>
        <p className="text-sm text-app-hint">{template.description}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {needs('period') && (
          <>
            <Field label="Davr boshi">
              <Input type="date" value={values.date_from} onChange={set('date_from')} />
            </Field>
            <Field label="Davr oxiri">
              <Input type="date" value={values.date_to} onChange={set('date_to')} />
            </Field>
          </>
        )}
        {needs('faculty') && (
          <Field label="Fakultet">
            <Select value={values.faculty_id ?? ''} onChange={set('faculty_id')}>
              <option value="">Hammasi</option>
              {faculties.map((faculty) => (
                <option key={faculty.id} value={faculty.id}>
                  {faculty.name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        {needs('course') && (
          <Field label="Kurs">
            <Select value={values.course ?? ''} onChange={set('course')}>
              <option value="">Hammasi</option>
              {[1, 2, 3, 4, 5, 6].map((course) => (
                <option key={course} value={course}>
                  {course}-kurs
                </option>
              ))}
            </Select>
          </Field>
        )}
        {needs('group') && (
          <Field label="Guruh">
            <Input value={values.group_name ?? ''} onChange={set('group_name')} placeholder="Hammasi" maxLength={32} />
          </Field>
        )}
        {needs('event') && (
          <Field label="Tadbir *">
            <Select value={values.event_id ?? ''} onChange={set('event_id')}>
              <option value="">Tanlang</option>
              {events.state.status === 'success' &&
                events.state.data?.items.map((event) => (
                  <option key={event.id} value={event.id}>
                    {formatDate(event.starts_at)} — {event.title}
                  </option>
                ))}
            </Select>
          </Field>
        )}
        {needs('test') && (
          <Field label="Test *">
            <Select value={values.test_id ?? ''} onChange={set('test_id')}>
              <option value="">Tanlang</option>
              {tests.state.status === 'success' &&
                tests.state.data?.items.map((test) => (
                  <option key={test.id} value={test.id}>
                    {formatDate(test.starts_at)} — {test.title}
                  </option>
                ))}
            </Select>
          </Field>
        )}
        {needs('report') && (
          <Field label="Hisobot *">
            <Select value={values.report_id ?? ''} onChange={set('report_id')}>
              <option value="">Tanlang</option>
              {reports.state.status === 'success' &&
                reports.state.data?.items.map((report) => (
                  <option key={report.id} value={report.id}>
                    {formatDate(report.created_at)} — {report.title}
                  </option>
                ))}
            </Select>
          </Field>
        )}
      </div>
      <InlineError message={error} />
      {done && <p className="text-sm text-emerald-600">{done}</p>}
      <div className="flex flex-wrap gap-2">
        {template.formats.map((format) => (
          <div key={format} className="flex overflow-hidden rounded-lg border border-app-border">
            {!insideTelegram && (
              <Button
                variant="ghost"
                className="rounded-none"
                loading={busy === `get:${format}`}
                disabled={busy !== null || missing}
                onClick={() => void save(format)}
                title="Kompyuterga yuklab olish"
              >
                {FORMAT_LABEL[format]} 📥
              </Button>
            )}
            <Button
              variant="ghost"
              className="rounded-none border-l border-app-border"
              loading={busy === `send:${format}`}
              disabled={busy !== null || missing}
              onClick={() => void send(format)}
              title="Bot chatingizga yuborish"
            >
              {insideTelegram ? FORMAT_LABEL[format] : ''} 📨 Botga
            </Button>
          </div>
        ))}
      </div>
    </Card>
  )
}

/** «📄 Hujjatlar»: the list of document templates; each one in Excel, Word or PDF, downloaded or sent to the bot. */
export function DocumentsPage() {
  const { api } = useSession()
  const templates = useAsync((signal) => api<DocumentTemplate[]>('/api/v1/admin/documents', { signal }))
  const faculties = useAsync((signal) => api<Faculty[]>('/api/v1/admin/faculties', { signal }))
  return (
    <>
      <PageHeader
        title="Hujjatlar"
        subtitle="Barcha hisobot va ro'yxatlar shablonlari: Excel, Word yoki PDF. Telefonda «📨 Botga» — fayl bot chatingizga keladi."
      />
      {templates.state.status === 'loading' && <LoadingState />}
      {templates.state.status === 'error' && <ErrorState message={templates.state.error.message} onRetry={templates.reload} />}
      {templates.state.status === 'success' && (
        <div className="grid gap-4 xl:grid-cols-2">
          {templates.state.data.map((template) => (
            <TemplateCard key={template.code} template={template} faculties={faculties.state.status === 'success' ? faculties.state.data : []} />
          ))}
        </div>
      )}
    </>
  )
}
