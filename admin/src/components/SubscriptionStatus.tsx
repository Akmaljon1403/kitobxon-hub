import { Card } from './ui'
import { useAsync } from '../hooks/useAsync'
import { useSession } from '../store/session'

interface ChannelRight {
  chat_id: string
  url: string
  ok: boolean
  problem: string
}
interface Status {
  required: boolean
  enforceable: boolean
  channels: ChannelRight[]
}

/** Shows whether the «majburiy obuna» gate is really working: the bot must be an administrator of
 *  every required channel, otherwise the check is silently skipped and members get in without it. */
export function SubscriptionStatusCard() {
  const { api } = useSession()
  const { state } = useAsync((signal) => api<Status>('/api/v1/admin/subscription/status', { signal }))
  if (state.status !== 'success') return null
  const status = state.data

  if (!status.required) {
    return (
      <Card className="border-l-4 border-l-app-border p-4 text-sm">
        <p className="font-semibold">📢 Majburiy obuna — o'chirilgan</p>
        <p className="mt-1 text-app-hint">
          Hozir a'zolar kanalga obuna bo'lmasa ham botdan foydalana oladi. Yoqish uchun pastdagi «...uchun kanal(lar)ga obuna
          majburiy» sozlamasini «Ha» qiling va botni kanalga administrator qiling.
        </p>
      </Card>
    )
  }

  if (status.enforceable) {
    return (
      <Card className="border-l-4 border-l-emerald-500 bg-emerald-50 p-4 text-sm dark:bg-emerald-950/30">
        <p className="font-semibold text-emerald-700 dark:text-emerald-300">✅ Majburiy obuna ishlayapti</p>
        <p className="mt-1 text-app-hint">
          Obuna bo'lmagan yoki kanaldan chiqib ketgan a'zoga bot «Davom etish uchun kanalga obuna bo'ling» deb chiqaradi.
        </p>
        <ul className="mt-2 space-y-1">
          {status.channels.map((channel) => (
            <li key={channel.chat_id}>✅ {channel.chat_id}</li>
          ))}
        </ul>
      </Card>
    )
  }

  return (
    <Card className="border-l-4 border-l-app-danger bg-red-50 p-4 text-sm dark:bg-red-950/30">
      <p className="font-semibold text-app-danger">⚠️ Majburiy obuna YOQILGAN, lekin ishlamayapti</p>
      <p className="mt-1">
        Shuning uchun a'zolar hozir kanalga obuna bo'lmasa ham botdan foydalanyapti. Sabab: bot quyidagi kanal(lar)ni
        tekshira olmayapti. <b>Botni o'sha kanalga administrator qiling</b> — keyin tekshiruv o'z-o'zidan ishlaydi.
      </p>
      {status.channels.length === 0 ? (
        <p className="mt-2 text-app-hint">
          Kanal ko'rsatilmagan. Pastdagi «Obuna bo'lish shart bo'lgan kanallar» ga kanal manzilini yozing (masalan
          @kanal).
        </p>
      ) : (
        <ul className="mt-2 space-y-1">
          {status.channels.map((channel) => (
            <li key={channel.chat_id}>
              {channel.ok ? '✅' : '❌'} {channel.chat_id}
              {!channel.ok && channel.problem && <span className="text-app-danger"> — {channel.problem}</span>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
