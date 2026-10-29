import { useCallback, useEffect, useState } from 'react'

import { Icon } from '../components/Icon'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, PageTitle } from '../components/ui'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import { navigate } from '../utils/router'
import { haptic } from '../utils/telegram'

/** «🪪 Kitobxonlik kartam»: the reader's year in one picture, sent to the bot chat to share. */
export function ReadingCardPage() {
  const { api, download } = useAuth()
  const goBack = useCallback(() => navigate('/profile'), [])
  useBackButton(goBack)
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)

  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    setFailed(false)
    setSrc(null)
    download('/api/v1/me/reading-card.png')
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
  }, [download, attempt])

  async function send() {
    setBusy(true)
    setNotice(null)
    try {
      await api('/api/v1/me/reading-card/send', { method: 'POST' })
      haptic('success')
      setNotice({ text: '✅ Kartangiz bot chatiga yuborildi — u yerdan do‘stlaringizga ulashing.' })
    } catch (err) {
      setNotice({ text: err instanceof ApiError ? err.message : 'Yuborib bo‘lmadi', error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div>
        <PageTitle icon="id-card">Kitobxonlik kartam</PageTitle>
        <p className="px-1 text-sm text-app-hint">O‘qigan kitoblar, betlar, seriya, ball va yutuqlaringiz — bitta rasmda</p>
      </div>
      {failed ? (
        <ErrorState message="Kartani tayyorlab bo‘lmadi." onRetry={() => setAttempt((value) => value + 1)} />
      ) : src ? (
        <img src={src} alt="Kitobxonlik kartam" className="w-full rounded-2xl shadow" />
      ) : (
        <LoadingState label="Karta chizilmoqda…" />
      )}
      {notice && <p className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-link'}`}>{notice.text}</p>}
      <Button loading={busy} disabled={!src} onClick={() => void send()}>
        <Icon name="send" size={18} />Botga yuborish va ulashish
      </Button>
      <Card className="text-sm text-app-hint">
        Karta har safar yangi raqamlar bilan chiziladi. Botda <b>/kartam</b> deb yozsangiz ham keladi.
      </Card>
    </div>
  )
}
