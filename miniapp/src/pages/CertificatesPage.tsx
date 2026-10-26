import { useCallback, useEffect, useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { API_BASE, ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Certificate, CertificateDesign } from '../types/api'
import { formatDate } from '../utils/format'
import { sendToChat } from '../utils/files'
import { navigate } from '../utils/router'
import { getWebApp, haptic } from '../utils/telegram'

const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }

/** Anyone who opens the link sees that the certificate is genuine — free for every member. */
function share(certificate: Certificate) {
  if (!certificate.verify_url) return
  const text = `🎓 ${certificate.title} — Kitobxonlar klubi sertifikati`
  const link = `https://t.me/share/url?url=${encodeURIComponent(certificate.verify_url)}&text=${encodeURIComponent(text)}`
  const webApp = getWebApp()
  if (webApp) webApp.openTelegramLink(link)
  else window.open(link, '_blank')
}

function CertificateRow({ certificate }: { certificate: Certificate }) {
  return (
    <button type="button" className="text-left" onClick={() => navigate(`/certificates/${certificate.id}`)}>
      <Card className="flex items-start gap-3">
        <span aria-hidden className="text-4xl leading-none">
          {(certificate.place && MEDALS[certificate.place]) || '🎓'}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold leading-snug">{certificate.title}</h2>
          <p className="mt-1 text-xs text-app-hint">
            {formatDate(certificate.issued_at)} · kod: <span className="font-mono">{certificate.code}</span>
          </p>
        </div>
        <span className="text-app-link">→</span>
      </Card>
    </button>
  )
}

/** The certificate picture (free, marked «ko'rish uchun»). */
function Preview({ certificateId, design, version }: { certificateId: string; design: string | null; version: number }) {
  const { download } = useAuth()
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    setSrc(null)
    setFailed(false)
    download(`/api/v1/me/certificates/${certificateId}/preview.png${design ? `?design=${design}` : ''}`)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [download, certificateId, design, version])
  if (failed) return <p className="py-8 text-center text-sm text-app-hint">Rasmni yuklab bo'lmadi.</p>
  if (!src) return <LoadingState label="Sertifikat chizilmoqda…" />
  return <img src={src} alt="Sertifikat" className="w-full rounded-xl border border-app-hint/20" />
}

function CertificateDetail({ certificateId }: { certificateId: string }) {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/certificates'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<Certificate>(`/api/v1/me/certificates/${certificateId}`, { signal }), [certificateId])
  const designs = useAsync((signal) => api<CertificateDesign[]>('/api/v1/me/certificate-designs', { signal }))
  const [trying, setTrying] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState<'send' | 'design' | null>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const certificate = state.data
  const rights = certificate.rights
  const shown = trying ?? certificate.design ?? null

  async function run(action: 'send' | 'design', work: () => Promise<string>) {
    setBusy(action)
    setNotice(null)
    try {
      setNotice({ text: await work() })
      haptic('success')
    } catch (error) {
      haptic('error')
      setNotice({ text: error instanceof ApiError ? error.message : "Bajarib bo'lmadi.", error: true })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col gap-2">
        <h1 className="text-lg font-semibold leading-snug">
          {(certificate.place && MEDALS[certificate.place]) || '🎓'} {certificate.title}
        </h1>
        <p className="text-sm text-app-hint">{certificate.description}</p>
        <p className="text-xs text-app-hint">
          {formatDate(certificate.issued_at)} · tekshirish kodi: <span className="font-mono">{certificate.code}</span>
        </p>
        <Preview certificateId={certificate.id} design={trying} version={version} />
        <p className="text-center text-xs text-app-hint">
          Bu — yagona sertifikat: qaysi dizaynda yuklab olsangiz ham, kodi va QR tekshiruvi bitta.
        </p>
      </Card>

      <Card className="flex flex-col gap-2">
        {rights?.can_download ? (
          <Button
            loading={busy === 'send'}
            disabled={busy !== null}
            onClick={() =>
              void run('send', async () => {
                await sendToChat(api, { kind: 'certificate', id: certificate.id })
                reload()
                return '✅ PDF bot chatiga yuborildi — u yerdan saqlab, chop eting.'
              })
            }
          >
            📥 PDF'ni olish (botga yuboriladi)
          </Button>
        ) : (
          <Button onClick={() => navigate('/premium')}>💎 PDF yuklab olish — Premium bilan</Button>
        )}
        <p className="text-center text-xs text-app-hint">
          {rights?.downloads_left == null
            ? '💎 Premium: cheksiz yuklab olasiz.'
            : rights.downloads_left > 0
              ? `Bepul yuklab olish: yana ${rights.downloads_left} marta.`
              : "Bepul yuklab olish imkoniyati tugadi. Ko'rish va ulashish — bepul."}
        </p>
        {certificate.verify_url && (
          <Button variant="ghost" className="px-2 text-sm" onClick={() => share(certificate)}>
            🔗 Tasdiqlash havolasini ulashish (bepul)
          </Button>
        )}
      </Card>

      {designs.state.status === 'success' && (
        <Card className="flex flex-col gap-2">
          <SectionTitle>🎨 Dizayn</SectionTitle>
          <p className="text-xs text-app-hint">
            {rights?.premium
              ? `Bosib ko'ring, yoqqanini tanlang. Yana ${rights.design_changes_left} marta almashtirish mumkin.`
              : "Ko'rib chiqish bepul. Dizaynni almashtirish — 💎 Premium imkoniyati."}
          </p>
          <div className="grid grid-cols-3 gap-2">
            {designs.state.data.map((design) => (
              <button
                key={design.code}
                type="button"
                onClick={() => setTrying(design.code === certificate.design ? null : design.code)}
                className={`flex flex-col items-center gap-1 rounded-lg p-1 text-xs ${shown === design.code ? 'ring-2 ring-app-link' : ''}`}
              >
                <img src={`${API_BASE}/api/v1/meta/certificate-designs/${design.code}.png`} alt="" className="w-full rounded" loading="lazy" />
                <span>
                  {design.title}
                  {design.code === certificate.design ? ' ✓' : ''}
                </span>
              </button>
            ))}
          </div>
          {trying && (
            rights?.can_change_design ? (
              <Button
                loading={busy === 'design'}
                onClick={() =>
                  void run('design', async () => {
                    await api(`/api/v1/me/certificates/${certificate.id}/design`, { method: 'PUT', body: { design: trying } })
                    setTrying(null)
                    setVersion((value) => value + 1)
                    reload()
                    return '✅ Dizayn saqlandi.'
                  })
                }
              >
                ✅ Shu dizaynni tanlash
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => navigate('/premium')}>
                {rights?.premium ? 'Almashtirish imkoniyati tugagan' : '💎 Tanlash — Premium bilan'}
              </Button>
            )
          )}
        </Card>
      )}

      {notice && (
        <p role={notice.error ? 'alert' : 'status'} className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-hint'}`}>
          {notice.text}
        </p>
      )}
    </div>
  )
}

/** «Sertifikatlarim»: every certificate can be seen here; the PDF is Premium (or a few free downloads). */
export function CertificatesPage({ certificateId }: { certificateId?: string }) {
  return certificateId ? <CertificateDetail certificateId={certificateId} /> : <CertificateList />
}

function CertificateList() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/profile'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<Certificate[]>('/api/v1/me/certificates', { signal }))

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  return (
    <div className="flex flex-col gap-3">
      <h1 className="font-serif text-2xl font-bold">🎓 Sertifikatlarim</h1>
      {state.data.length === 0 ? (
        <EmptyState icon="🎓" title="Hozircha sertifikat yo'q">
          Testda 1-, 2- yoki 3-o'rinni oling (tadbir testida — davomatdan o'tib) yoki oy yakunida reytingning eng faol
          uchligiga kiring — sertifikat avtomatik beriladi.
        </EmptyState>
      ) : (
        state.data.map((certificate) => <CertificateRow key={certificate.id} certificate={certificate} />)
      )}
      <p className="text-center text-xs text-app-hint">
        <Badge tone="info">Bepul</Badge> ko'rish va tasdiq havolasini ulashish · <Badge tone="warning">💎</Badge> PDF va dizayn tanlash
      </p>
    </div>
  )
}
