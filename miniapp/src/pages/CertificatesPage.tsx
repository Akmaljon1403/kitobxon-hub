import { useCallback, useState } from 'react'

import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { Certificate } from '../types/api'
import { formatDate } from '../utils/format'
import { saveDocument, sendToChat } from '../utils/files'
import { navigate } from '../utils/router'
import { haptic } from '../utils/telegram'

const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' }

function CertificateCard({ certificate }: { certificate: Certificate }) {
  const { api } = useAuth()
  const [busy, setBusy] = useState<'save' | 'send' | null>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)

  async function run(action: 'save' | 'send') {
    setBusy(action)
    setNotice(null)
    const ref = { kind: 'certificate' as const, id: certificate.id }
    try {
      const how = action === 'save' ? await saveDocument(api, ref) : (await sendToChat(api, ref), 'chat')
      setNotice({ text: how === 'dialog' ? '✅ Saqlash oynasi ochildi.' : '✅ PDF bot chatiga yuborildi.' })
      haptic('success')
    } catch (error) {
      haptic('error')
      setNotice({ text: error instanceof ApiError ? error.message : "Bajarib bo'lmadi.", error: true })
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-start gap-3">
        <span aria-hidden className="text-4xl leading-none">
          {(certificate.place && MEDALS[certificate.place]) || '🎓'}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold leading-snug">{certificate.title}</h2>
          <p className="mt-1 text-sm text-app-hint">{certificate.description}</p>
          <p className="mt-1 text-xs text-app-hint">
            {formatDate(certificate.issued_at)} · kod: <span className="font-mono">{certificate.code}</span>
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Button className="whitespace-nowrap px-2 text-sm" loading={busy === 'save'} disabled={busy !== null} onClick={() => void run('save')}>
          📥 Yuklab olish
        </Button>
        <Button
          variant="secondary"
          className="whitespace-nowrap px-2 text-sm"
          loading={busy === 'send'}
          disabled={busy !== null}
          onClick={() => void run('send')}
        >
          📤 Chatga yuborish
        </Button>
      </div>
      {notice && (
        <p role={notice.error ? 'alert' : 'status'} className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-hint'}`}>
          {notice.text}
        </p>
      )}
    </Card>
  )
}

/** «Sertifikatlarim»: certificates for winning places, with PDF download. */
export function CertificatesPage() {
  const { api } = useAuth()
  const goBack = useCallback(() => navigate('/profile'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<Certificate[]>('/api/v1/me/certificates', { signal }))

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-xl font-semibold">🎓 Sertifikatlarim</h1>
      {state.data.length === 0 ? (
        <EmptyState icon="🎓" title="Hozircha sertifikat yo'q">
          Testda 1-, 2- yoki 3-o'rinni oling (tadbir testida — davomatdan o'tib) yoki oy yakunida reytingning eng faol
          uchligiga kiring — sertifikat avtomatik beriladi.
        </EmptyState>
      ) : (
        state.data.map((certificate) => <CertificateCard key={certificate.id} certificate={certificate} />)
      )}
      <p className="text-center text-xs text-app-hint">
        Har bir sertifikatda QR kod bor — uni skanerlagan kishi sertifikat haqiqiyligini tekshira oladi.
      </p>
    </div>
  )
}
