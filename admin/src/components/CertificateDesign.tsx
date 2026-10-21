import { useEffect, useRef, useState } from 'react'

import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { AdminEvent } from '../types/api'
import { Button, InlineError } from './ui'

/**
 * «🎓 Sertifikat dizayni» of an event or a test: a sample of the winners' certificate, and the club's own
 * background picture (admins until the start, the super admin until the test ends).
 */
export function CertificateDesignBox({ base, hasBackground, onChanged }: { base: string; hasBackground: boolean; onChanged: () => void }) {
  const { api, download } = useSession()
  const [src, setSrc] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const [has, setHas] = useState(hasBackground)

  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    setSrc(null)
    download(`${base}/certificate-preview.png`)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [base, download, version])

  async function run(work: () => Promise<unknown>, next: boolean) {
    setBusy(true)
    setError(null)
    try {
      await work()
      setHas(next)
      setVersion((value) => value + 1)
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bajarib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  function upload(file: File | undefined) {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    void run(() => api(`${base}/certificate-background`, { method: 'PUT', body: form }), true)
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-app-border p-3">
      <p className="text-sm font-medium">🎓 G'oliblar sertifikati</p>
      <p className="text-xs text-app-hint">
        {has
          ? "Klub dizayni yuklangan: ism, matn, sana va QR kod shu rasm ustiga yoziladi."
          : "Odatda 12 ta tayyor dizayndan navbatdagisi ishlatiladi. O'zingizning sertifikat rasmingizni (A4, yotiq) yuklasangiz, matn uning ustiga yoziladi. Administrator — tadbir/test boshlangunicha, bosh administrator — test yakunlangunicha yuklay oladi."}
      </p>
      {src ? <img src={src} alt="Sertifikat namunasi" className="w-full max-w-xl rounded border border-app-border" /> : <p className="text-xs text-app-hint">Namuna chizilmoqda…</p>}
      <div className="flex flex-wrap gap-2">
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
        <Button variant="secondary" loading={busy} onClick={() => input.current?.click()}>
          {has ? '🖼 Boshqa rasm' : '🖼 O\'z dizaynimni yuklash'}
        </Button>
        {has && (
          <Button variant="ghost" className="text-app-danger" disabled={busy} onClick={() => void run(() => api(`${base}/certificate-background`, { method: 'DELETE' }), false)}>
            Tayyor dizaynlarga qaytish
          </Button>
        )}
      </div>
      <InlineError message={error} />
    </div>
  )
}

interface DesignItem {
  code: string
  title: string
}
interface TemplateItem {
  id: string
  name: string
}

/**
 * «🎓 G'oliblar sertifikati» of an event — the full picker (P4): a live sample, and the choice between
 * the next standard design in turn, a specific standard design (the one that is next is marked), one of
 * the admin's own saved templates, or the admin's own uploaded picture.
 */
export function CertificatePicker({ event, onChanged }: { event: AdminEvent; onChanged: () => void }) {
  const { api, download } = useSession()
  const base = `/api/v1/admin/events/${event.id}`
  const [src, setSrc] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const [choice, setChoice] = useState({
    background: event.certificate_background,
    design: event.certificate_design,
    templateId: event.certificate_template_id,
  })

  const designs = useAsync((signal) => api<DesignItem[]>('/api/v1/meta/certificate-designs', { signal }))
  const next = useAsync((signal) => api<DesignItem>('/api/v1/admin/certificate-next-design', { signal }))
  const templates = useAsync((signal) => api<TemplateItem[]>('/api/v1/admin/certificate-templates', { signal }))

  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    setSrc(null)
    download(`${base}/certificate-preview.png`)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [base, download, version])

  async function run(work: () => Promise<unknown>, nextChoice: typeof choice) {
    setBusy(true)
    setError(null)
    try {
      await work()
      setChoice(nextChoice)
      setVersion((value) => value + 1)
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bajarib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  function chooseDesign(code: string | null) {
    void run(() => api(`${base}/certificate-choice`, { method: 'PUT', body: { design: code } }), {
      background: false,
      design: code,
      templateId: null,
    })
  }
  function chooseTemplate(id: string) {
    void run(() => api(`${base}/certificate-choice`, { method: 'PUT', body: { template_id: id } }), {
      background: false,
      design: null,
      templateId: id,
    })
  }
  function upload(file: File | undefined) {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    void run(() => api(`${base}/certificate-background`, { method: 'PUT', body: form }), { background: true, design: null, templateId: null })
  }

  const mode = choice.background ? 'custom' : choice.templateId ? 'template' : choice.design ? 'design' : 'auto'
  const nextCode = next.state.status === 'success' ? next.state.data.code : null
  const nextTitle = next.state.status === 'success' ? next.state.data.title : null
  const chip = (active: boolean) =>
    `rounded-lg border px-3 py-1.5 text-sm transition ${active ? 'border-app-accent bg-app-accent/10 font-medium text-app-accent' : 'border-app-border hover:border-app-accent/50'}`

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-app-border p-3">
      <div>
        <p className="text-sm font-medium">🎓 G'oliblar sertifikati dizayni</p>
        <p className="text-xs text-app-hint">
          Bot sertifikatni shu ko'rinishda chizadi. Tanlamasangiz — tayyor dizaynlar navbat bilan ishlatiladi.
          O'zingiz tanlang yoki «Sertifikatlar» bo'limida yaratgan shablonlaringizdan birini qo'ying.
        </p>
      </div>

      {src ? (
        <img src={src} alt="Sertifikat namunasi" className="w-full max-w-xl rounded border border-app-border" />
      ) : (
        <p className="text-xs text-app-hint">Namuna chizilmoqda…</p>
      )}

      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={busy} className={chip(mode === 'auto')} onClick={() => chooseDesign(null)}>
          🔄 Navbatdagi{nextTitle ? ` — «${nextTitle}»` : ''}
        </button>
        <button type="button" disabled={busy} className={chip(mode === 'custom')} onClick={() => input.current?.click()}>
          🖼 O'z rasmim
        </button>
      </div>

      <div className="flex flex-col gap-1.5">
        <p className="text-xs font-medium text-app-hint">Tayyor dizaynlar (navbatdagisi belgilangan):</p>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {designs.state.status === 'success' &&
            designs.state.data.map((design) => {
              const active = mode === 'design' && choice.design === design.code
              return (
                <button
                  key={design.code}
                  type="button"
                  disabled={busy}
                  onClick={() => chooseDesign(design.code)}
                  className={`relative overflow-hidden rounded-lg border-2 text-left transition ${active ? 'border-app-accent' : 'border-transparent hover:border-app-accent/40'}`}
                >
                  <img src={`/api/v1/meta/certificate-designs/${design.code}.png`} alt={design.title} className="aspect-[297/210] w-full object-cover" loading="lazy" />
                  <span className="block truncate px-1 py-0.5 text-[11px]">
                    {design.code === nextCode ? '➡️ ' : ''}
                    {design.title}
                  </span>
                  {active && <span className="absolute right-1 top-1 rounded bg-app-accent px-1 text-[10px] text-white">✓</span>}
                </button>
              )
            })}
        </div>
      </div>

      {templates.state.status === 'success' && templates.state.data.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-medium text-app-hint">Mening shablonlarim:</p>
          <div className="flex flex-wrap gap-2">
            {templates.state.data.map((template) => (
              <button key={template.id} type="button" disabled={busy} className={chip(mode === 'template' && choice.templateId === template.id)} onClick={() => chooseTemplate(template.id)}>
                📄 {template.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
      <InlineError message={error} />
    </div>
  )
}
