import { useCallback, useState } from 'react'

import { Giveaways } from '../components/Giveaways'
import { EmptyState, ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { MemberReward } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate } from '../utils/router'
import { confirmAction, haptic } from '../utils/telegram'

const ICONS: Record<MemberReward['type'], string> = {
  BOOK: '📚',
  CERTIFICATE: '📜',
  SUBSCRIPTION_CODE: '🔑',
  PARTNER_DISCOUNT: '🏷️',
  OTHER: '🎁',
}

function RewardCard({ reward, onChanged }: { reward: MemberReward; onChanged: () => void }) {
  const { api } = useAuth()
  const [code, setCode] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  async function reveal() {
    setBusy(true)
    setError(null)
    try {
      const result = await api<{ code: string }>(`/api/v1/me/rewards/${reward.id}/code`, { method: 'POST' })
      setCode(result.code)
      haptic('success')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kodni ochib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function redeemed() {
    if (!(await confirmAction("Sovg'adan foydalandingizmi?"))) return
    try {
      await api(`/api/v1/me/rewards/${reward.id}/redeemed`, { method: 'POST' })
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    }
  }

  const used = reward.status === 'REDEEMED'
  return (
    <Card className={`flex flex-col gap-2 ${used ? 'opacity-70' : ''}`}>
      <div className="flex items-start gap-3">
        <span aria-hidden className="text-3xl">
          {ICONS[reward.type]}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{reward.title}</p>
          {reward.value && <p className="text-sm text-app-link">{reward.value}</p>}
          {reward.description && <p className="whitespace-pre-line text-sm text-app-hint">{reward.description}</p>}
          <p className="mt-1 text-xs text-app-hint">
            Berilgan: {formatDate(reward.assigned_at)}
            {reward.expires_at ? ` · Amal qiladi: ${formatDate(reward.expires_at)} gacha` : ''}
          </p>
        </div>
        {used && <Badge tone="success">Foydalanilgan</Badge>}
      </div>
      {reward.has_code &&
        (code ? (
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard?.writeText(code).then(() => setCopied(true))
            }}
            className="rounded-xl border-2 border-dashed border-app-button/50 bg-app-surface py-3 text-center font-mono text-lg font-semibold tracking-wider"
          >
            {code}
            <span className="block font-sans text-xs font-normal tracking-normal text-app-hint">{copied ? '✓ Nusxalandi' : 'Nusxalash uchun bosing'}</span>
          </button>
        ) : (
          !used && (
            <Button variant="secondary" loading={busy} onClick={() => void reveal()}>
              🔑 Kodni ko'rsatish
            </Button>
          )
        ))}
      {!used && (reward.status === 'DELIVERED' || code || !reward.has_code) && (
        <Button variant="ghost" onClick={() => void redeemed()}>
          ✓ Foydalandim
        </Button>
      )}
      {reward.has_code && <p className="text-xs text-app-hint">Kod faqat sizga ko'rinadi — uni boshqalarga bermang.</p>}
      {error && (
        <p role="alert" className="text-sm text-app-danger">
          {error}
        </p>
      )}
    </Card>
  )
}

export function RewardsPage() {
  const { api } = useAuth()
  const { state, reload } = useAsync((signal) => api<MemberReward[]>('/api/v1/me/rewards', { signal }))
  const goBack = useCallback(() => navigate('/profile'), [])
  useBackButton(goBack)
  return (
    <>
      <h1 className="px-1 pt-1 text-xl font-semibold">🎁 Sovg'alarim</h1>
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.length === 0 && (
        <EmptyState icon="🎁" title="Hozircha sovg'alar yo'q">
          Faol qatnashing — reyting yetakchilari va faol kitobxonlar klub sovg'alari bilan taqdirlanadi.
        </EmptyState>
      )}
      {state.status === 'success' && state.data.map((reward) => <RewardCard key={reward.id} reward={reward} onChanged={reload} />)}
      <Giveaways />
    </>
  )
}
