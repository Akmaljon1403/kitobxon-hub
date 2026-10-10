import { useState } from 'react'

import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import { saveDocument } from '../utils/files'
import { navigate } from '../utils/router'
import { haptic } from '../utils/telegram'
import { TrialBadge, useFeature } from './FeatureGate'
import { Button, Card } from './ui'

/** «Kitobxonlik portfoliosi»: books, certificates, tests, events and achievements in one PDF. */
export function PortfolioCard() {
  const { api } = useAuth()
  const access = useFeature('portfolio')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  async function statement(format: 'pdf' | 'docx') {
    setBusy(true)
    setNotice(null)
    try {
      await api('/api/v1/me/statement/send', { method: 'POST', body: { format } })
      setNotice({ text: `✅ Ma'lumotnoma (${format === 'pdf' ? 'PDF' : 'Word'}) bot chatiga yuborildi.` })
      haptic('success')
    } catch (error) {
      haptic('error')
      setNotice({ text: error instanceof ApiError ? error.message : "Tayyorlab bo'lmadi.", error: true })
    } finally {
      setBusy(false)
    }
  }

  if (access === 'off')
    return (
      <Card className="flex flex-col gap-2">
        <StatementButtons busy={busy} onPick={(format) => void statement(format)} />
        {notice && <p className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-hint'}`}>{notice.text}</p>}
      </Card>
    )

  async function save() {
    setBusy(true)
    setNotice(null)
    try {
      await saveDocument(api, { kind: 'portfolio' })
      setNotice({ text: '✅ Portfolio bot chatiga yuborildi (PDF va Word).' })
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
          <p className="flex flex-wrap items-center gap-1.5 font-semibold">
            Kitobxonlik portfoliosi <TrialBadge code="portfolio" />
          </p>
          <p className="text-sm text-app-hint">
            O'qigan kitoblaringiz, sertifikatlar, test natijalari va yutuqlar — bitta chiroyli PDF. Rezyume va grantlar uchun.
          </p>
        </div>
      </div>
      {access === 'on' ? (
        <Button loading={busy} disabled={busy} onClick={() => void save()}>
          📥 Botga yuborish (PDF + Word)
        </Button>
      ) : (
        <Button variant="secondary" onClick={() => navigate('/premium')}>
          💎 Premium bilan ochiladi
        </Button>
      )}
      <StatementButtons busy={busy} onPick={(format) => void statement(format)} />
      {notice && (
        <p role={notice.error ? 'alert' : 'status'} className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-hint'}`}>
          {notice.text}
        </p>
      )}
    </Card>
  )
}

/** «Faoliyat ma'lumotnomasi»: this study year's activity for the institute — free for everyone. */
function StatementButtons({ busy, onPick }: { busy: boolean; onPick: (format: 'pdf' | 'docx') => void }) {
  return (
    <div className="flex flex-col gap-1.5 border-t border-app-hint/15 pt-2">
      <p className="text-sm">
        📄 <b>Faoliyat ma'lumotnomasi</b> — o'quv yili davomidagi tadbir, test, kitob va ballaringiz; QR kod bilan (institutga topshirish
        uchun).
      </p>
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" disabled={busy} onClick={() => onPick('pdf')}>
          📕 PDF
        </Button>
        <Button variant="secondary" disabled={busy} onClick={() => onPick('docx')}>
          📝 Word
        </Button>
      </div>
    </div>
  )
}
