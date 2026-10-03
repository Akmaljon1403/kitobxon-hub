import { useState } from 'react'

import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import { saveDocument } from '../utils/files'
import { navigate } from '../utils/router'
import { haptic } from '../utils/telegram'
import { useFeature } from './FeatureGate'
import { Button, Card } from './ui'

/** «Kitobxonlik portfoliosi»: books, certificates, tests, events and achievements in one PDF. */
export function PortfolioCard() {
  const { api } = useAuth()
  const access = useFeature('portfolio')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  if (access === 'off') return null

  async function save() {
    setBusy(true)
    setNotice(null)
    try {
      const how = await saveDocument(api, { kind: 'portfolio' })
      setNotice({ text: how === 'dialog' ? '✅ Saqlash oynasi ochildi.' : '✅ Portfolio bot chatiga yuborildi.' })
      haptic('success')
    } catch (error) {
      haptic('error')
      setNotice({ text: error instanceof ApiError ? error.message : "Tayyorlab bo'lmadi.", error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-start gap-3">
        <span aria-hidden className="text-3xl">
          🗂
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Kitobxonlik portfoliosi</p>
          <p className="text-sm text-app-hint">
            O'qigan kitoblaringiz, sertifikatlar, test natijalari va yutuqlar — bitta chiroyli PDF. Rezyume va grantlar uchun.
          </p>
        </div>
      </div>
      {access === 'on' ? (
        <Button loading={busy} disabled={busy} onClick={() => void save()}>
          📥 PDF yuklab olish
        </Button>
      ) : (
        <Button variant="secondary" onClick={() => navigate('/premium')}>
          💎 Premium bilan ochiladi
        </Button>
      )}
      {notice && (
        <p role={notice.error ? 'alert' : 'status'} className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-hint'}`}>
          {notice.text}
        </p>
      )}
    </Card>
  )
}
