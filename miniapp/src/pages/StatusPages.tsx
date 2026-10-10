import { useState } from 'react'

import { Button, Card } from '../components/ui'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { SubscriptionChannel } from '../types/api'
import { haptic, openBot, openTelegramLink } from '../utils/telegram'

function Shell({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-4 p-4">
      <Card className="flex flex-col items-center gap-3 py-8 text-center">
        <span aria-hidden className="text-5xl">
          {icon}
        </span>
        <h1 className="text-xl font-semibold">{title}</h1>
        {children}
      </Card>
    </main>
  )
}

export function NotRegisteredPage() {
  const { meta } = useAuth()
  return (
    <Shell icon="👋" title="Xush kelibsiz!">
      <p className="text-sm text-app-hint">
        Ilovadan foydalanish uchun avval botda ro'yxatdan o'ting. Bu 1–2 daqiqa vaqt oladi.
      </p>
      <Button onClick={() => openBot(meta?.bot_username ?? null, 'register')}>Ro'yxatdan o'tish</Button>
    </Shell>
  )
}

/** Members use the app while subscribed to the club channel(s): subscribe, then check again. */
export function SubscribePage({ channels }: { channels: SubscriptionChannel[] }) {
  const { api, retry } = useAuth()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function check() {
    setBusy(true)
    setMessage(null)
    try {
      const result = await api<{ ok: boolean; channels: SubscriptionChannel[] }>('/api/v1/me/subscription?fresh=true')
      if (result.ok) {
        haptic('success')
        retry()
        return
      }
      haptic('warning')
      setMessage(`Hali obuna ko'rinmayapti: ${result.channels.map((channel) => channel.title).join(', ')}. Obuna bo'lib, qayta bosing.`)
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : "Tekshirib bo'lmadi. Qayta urinib ko'ring.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell icon="📢" title="Bir qadam qoldi!">
      <p className="text-sm text-app-hint">
        Kitobxon Hub'dan foydalanish uchun klubimiz kanaliga obuna bo'ling: yangi kitoblar, tadbirlar, test natijalari va sovg'alar haqidagi
        xabarlar avval o'sha yerda chiqadi.
      </p>
      <div className="flex w-full flex-col gap-2">
        {channels.map((channel) => (
          <Button key={channel.url} variant="secondary" onClick={() => openTelegramLink(channel.url)}>
            📢 {channel.title}
          </Button>
        ))}
        <Button loading={busy} onClick={() => void check()}>
          ✅ Obuna bo'ldim
        </Button>
      </div>
      {message && (
        <p role="alert" className="text-sm text-app-danger">
          {message}
        </p>
      )}
    </Shell>
  )
}

export function OutsideTelegramPage() {
  const { meta } = useAuth()
  return (
    <Shell icon="📱" title="Kitobxon Hub">
      <p className="text-sm text-app-hint">Bu ilova Telegram ichida ishlaydi. Uni bot orqali oching.</p>
      {meta?.bot_username && (
        <Button onClick={() => openBot(meta.bot_username)}>Botni ochish (@{meta.bot_username})</Button>
      )}
    </Shell>
  )
}

export function AccountProblemPage({ message }: { message: string }) {
  return (
    <Shell icon="🔒" title="Kirish cheklangan">
      <p className="text-sm text-app-hint">{message}</p>
    </Shell>
  )
}

export function StartupErrorPage({ message }: { message: string }) {
  const { retry } = useAuth()
  return (
    <Shell icon="⚠️" title="Ulanib bo'lmadi">
      <p className="text-sm text-app-hint">{message}</p>
      <Button onClick={retry}>Qayta urinish</Button>
    </Shell>
  )
}

export function NotFoundPage() {
  return (
    <Card className="flex flex-col items-center gap-2 py-10 text-center">
      <span aria-hidden className="text-5xl">
        🧭
      </span>
      <h1 className="text-lg font-semibold">Sahifa topilmadi</h1>
      <p className="text-sm text-app-hint">Pastdagi menyudan bo'lim tanlang.</p>
    </Card>
  )
}
