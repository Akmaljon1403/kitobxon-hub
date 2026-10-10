import { useEffect, useRef, useState } from 'react'

import { ApiError } from '../services/api'
import { useSession } from '../store/session'
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
