import { useEffect, useState } from 'react'

import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import { saveDocument, sendToChat } from '../utils/files'
import { haptic } from '../utils/telegram'
import { Button, Card } from './ui'

/** «Kitobxon pasporti»: the ID card image drawn by the server, with save and send buttons. */
export function PassportCard() {
  const { api, download, me } = useAuth()
  const [src, setSrc] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState<'save' | 'send' | null>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)

  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    download('/api/v1/me/passport')
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
  }, [download])

  async function run(action: 'save' | 'send') {
    setBusy(action)
    setNotice(null)
    try {
      if (action === 'save') {
        const how = await saveDocument(api, { kind: 'passport' })
        setNotice({ text: how === 'dialog' ? '✅ Saqlash oynasi ochildi.' : '✅ Pasport bot chatiga yuborildi.' })
      } else {
        await sendToChat(api, { kind: 'passport' })
        setNotice({ text: '✅ Pasport bot chatiga yuborildi — u yerdan ulashishingiz mumkin.' })
      }
      haptic('success')
    } catch (error) {
      haptic('error')
      setNotice({ text: error instanceof ApiError ? error.message : "Bajarib bo'lmadi.", error: true })
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="font-semibold">🪪 Kitobxon pasporti</h2>
        {me && <span className="font-mono text-sm text-app-hint">{me.member_number}</span>}
      </div>
      <div className="aspect-[1200/756] w-full overflow-hidden rounded-xl bg-app-surface">
        {src ? (
          <img src={src} alt="Kitobxon pasporti" className="size-full object-cover" />
        ) : (
          <div className="flex size-full items-center justify-center p-4 text-center text-sm text-app-hint">
            {failed ? "Pasportni yuklab bo'lmadi. Sahifani yangilang." : 'Pasport tayyorlanmoqda…'}
          </div>
        )}
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
