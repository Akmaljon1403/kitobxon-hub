import { useEffect, useRef, useState } from 'react'

import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { PassportTheme } from '../types/api'
import { saveDocument, sendToChat } from '../utils/files'
import { navigate } from '../utils/router'
import { haptic } from '../utils/telegram'
import { Button, Card } from './ui'

type Busy = 'save' | 'send' | 'photo' | 'reset' | 'theme' | null

/**
 * «Kitobxon pasporti»: the ID card drawn by the server. The member can change the photo, and
 * premium members choose the design. Points and ranking are not printed: the QR code shows them live.
 */
export function PassportCard() {
  const { api, download, upload, me, refreshMe } = useAuth()
  const [src, setSrc] = useState<string | null>(null)
  const [version, setVersion] = useState(0)
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState<Busy>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const themes = useAsync((signal) => api<PassportTheme[]>('/api/v1/me/passport/themes', { signal }), [version])

  useEffect(() => {
    let url: string | null = null
    let cancelled = false
    setFailed(false)
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
  }, [download, version])

  async function run(action: Exclude<Busy, null>, work: () => Promise<string>) {
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

  function refresh() {
    setVersion((n) => n + 1)
    void refreshMe()
  }

  async function uploadPhoto(file: File) {
    await run('photo', async () => {
      const form = new FormData()
      form.append('file', file)
      await upload('/api/v1/me/passport/photo', form)
      refresh()
      return '✅ Rasm almashtirildi.'
    })
  }

  const premium = Boolean(me?.is_premium)
  const themeList = themes.state.status === 'success' ? themes.state.data : []

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="font-semibold">🪪 Kitobxon pasporti</h2>
        {me && <span className="font-mono text-sm text-app-hint">{me.member_number}</span>}
      </div>
      <div className="aspect-[1200/756] w-full overflow-hidden rounded-xl bg-app-surface">
        {src && !failed ? (
          <img src={src} alt="Kitobxon pasporti" className="size-full object-cover" />
        ) : (
          <div className="flex size-full items-center justify-center p-4 text-center text-sm text-app-hint">
            {failed ? "Pasportni yuklab bo'lmadi. Sahifani yangilang." : 'Pasport tayyorlanmoqda…'}
          </div>
        )}
      </div>
      <p className="text-xs text-app-hint">Ball, reyting va yutuqlaringiz QR kod orqali doim yangilangan holda ko'rinadi.</p>

      <div className="grid grid-cols-2 gap-2">
        <Button
          className="whitespace-nowrap px-2 text-sm"
          loading={busy === 'save'}
          disabled={busy !== null}
          onClick={() =>
            void run('save', async () =>
              (await saveDocument(api, { kind: 'passport' })) === 'dialog'
                ? '✅ Saqlash oynasi ochildi.'
                : '✅ Pasport bot chatiga yuborildi.',
            )
          }
        >
          📥 Yuklab olish
        </Button>
        <Button
          variant="secondary"
          className="whitespace-nowrap px-2 text-sm"
          loading={busy === 'send'}
          disabled={busy !== null}
          onClick={() =>
            void run('send', async () => {
              await sendToChat(api, { kind: 'passport' })
              return '✅ Pasport bot chatiga yuborildi — u yerdan ulashishingiz mumkin.'
            })
          }
        >
          📤 Chatga yuborish
        </Button>
        <Button
          variant="secondary"
          className="whitespace-nowrap px-2 text-sm"
          loading={busy === 'photo'}
          disabled={busy !== null}
          onClick={() => fileInput.current?.click()}
        >
          📷 Yangi rasm
        </Button>
        {me?.passport_photo ? (
          <Button
            variant="ghost"
            className="whitespace-nowrap px-2 text-sm"
            loading={busy === 'reset'}
            disabled={busy !== null}
            onClick={() =>
              void run('reset', async () => {
                await api('/api/v1/me/passport/photo', { method: 'DELETE' })
                refresh()
                return '✅ Telegram rasmingiz qaytarildi.'
              })
            }
          >
            ↩️ Telegram rasmi
          </Button>
        ) : (
          <span />
        )}
      </div>
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        className="hidden"
        aria-label="Pasport uchun rasm"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) void uploadPhoto(file)
          e.target.value = ''
        }}
      />

      {themeList.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">🎨 Dizayn {!premium && <span className="text-app-hint">— 💎 Premium</span>}</p>
          <div className="grid grid-cols-4 gap-2">
            {themeList.map((theme) => {
              const locked = theme.premium && !premium
              return (
                <button
                  key={theme.code}
                  type="button"
                  aria-pressed={theme.selected}
                  disabled={busy !== null}
                  onClick={() =>
                    locked
                      ? navigate('/premium')
                      : void run('theme', async () => {
                          await api('/api/v1/me/passport/theme', { method: 'PUT', body: { theme: theme.code } })
                          refresh()
                          return `✅ «${theme.title}» dizayni tanlandi.`
                        })
                  }
                  className={`flex flex-col items-center gap-1 rounded-xl p-1.5 text-[11px] ${theme.selected ? 'ring-2 ring-app-button' : ''}`}
                >
                  <span
                    className="relative block h-9 w-full rounded-lg"
                    style={{ background: `linear-gradient(135deg, ${theme.colors[0]}, ${theme.colors[1]})`, border: `2px solid ${theme.colors[2]}` }}
                  >
                    {locked && <span className="absolute inset-0 flex items-center justify-center text-sm">💎</span>}
                  </span>
                  {theme.title}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {notice && (
        <p role={notice.error ? 'alert' : 'status'} className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-hint'}`}>
          {notice.text}
        </p>
      )}
    </Card>
  )
}
