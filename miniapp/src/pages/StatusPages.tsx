import { Button, Card } from '../components/ui'
import { useAuth } from '../store/auth'
import { openBot } from '../utils/telegram'

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

const UPCOMING: Record<string, { icon: string; title: string; text: string }> = {
  achievements: { icon: '🏅', title: 'Yutuqlar', text: 'Qo\'lga kiritgan yutuqlaringiz shu yerda bo\'ladi.' },
}

export function UpcomingPage({ section }: { section: string }) {
  const info = UPCOMING[section] ?? { icon: '🧭', title: 'Sahifa topilmadi', text: 'Pastdagi menyudan bo\'lim tanlang.' }
  return (
    <Card className="flex flex-col items-center gap-2 py-10 text-center">
      <span aria-hidden className="text-5xl">
        {info.icon}
      </span>
      <h1 className="text-lg font-semibold">{info.title}</h1>
      <p className="text-sm text-app-hint">{info.text}</p>
      {UPCOMING[section] && (
        <p className="mt-2 rounded-full bg-app-surface px-3 py-1 text-xs text-app-hint">Bu bo'lim tez orada ishga tushadi</p>
      )}
    </Card>
  )
}
