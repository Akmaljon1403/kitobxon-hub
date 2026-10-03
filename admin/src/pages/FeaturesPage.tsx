import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Card, InlineError, PageHeader } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'

type Mode = 'OFF' | 'ALL' | 'PREMIUM'

interface Feature {
  code: string
  title: string
  description: string
  mode: Mode
  default: Mode
  premium_allowed: boolean
}

const MODES: { mode: Mode; label: string }[] = [
  { mode: 'OFF', label: "O'chiq" },
  { mode: 'ALL', label: 'Hammaga' },
  { mode: 'PREMIUM', label: '💎 Premium' },
]

/** Super admin: who may use each bot feature, with an announcement when one is switched on. */
export function FeaturesPage() {
  const { api } = useSession()
  const { state, reload } = useAsync((signal) => api<Feature[]>('/api/v1/admin/features', { signal }))
  const [announce, setAnnounce] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  async function change(feature: Feature, mode: Mode) {
    if (mode === feature.mode) return
    const tell = announce && mode !== 'OFF'
    const question =
      mode === 'OFF'
        ? `«${feature.title}» o'chirilsinmi? A'zolar uni ko'rmay qoladi.`
        : `«${feature.title}» ${mode === 'ALL' ? 'hamma a‘zolar' : 'Premium a‘zolar'} uchun yoqilsinmi?${tell ? "\n\nA'zolarga «Bot yangilandi» xabari yuboriladi." : ''}`
    if (!window.confirm(question)) return
    setBusy(feature.code)
    setError(null)
    setMessage(null)
    try {
      const result = await api<{ announced_to: number }>(`/api/v1/admin/features/${feature.code}`, {
        method: 'PUT',
        body: { mode, announce: tell },
      })
      setMessage(
        result.announced_to > 0
          ? `✓ Saqlandi. ${result.announced_to} nafar a'zoga xabar yuborilmoqda.`
          : '✓ Saqlandi.',
      )
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <PageHeader
        title="Imkoniyatlar"
        subtitle="Bot va ilovadagi har bir imkoniyatni yoqing, o'chiring yoki faqat Premium a'zolarga qoldiring. Yoqilganda a'zolarga «Tabriklaymiz, bot yangilandi!» xabari boradi."
      />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={announce} onChange={(e) => setAnnounce(e.target.checked)} className="size-4" />
        Yoqilganda a'zolarga e'lon yuborilsin
      </label>
      <InlineError message={error} />
      {message && <p className="text-sm text-emerald-600">{message}</p>}
      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && (
        <Card className="divide-y divide-app-border">
          {state.data.map((feature) => (
            <div key={feature.code} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="font-medium">
                  {feature.title}{' '}
                  {feature.mode !== feature.default && <Badge tone="info">o'zgartirilgan</Badge>}
                </p>
                <p className="text-sm text-app-hint">{feature.description}</p>
              </div>
              <div className="flex shrink-0 overflow-hidden rounded-lg border border-app-border" role="radiogroup" aria-label={feature.title}>
                {MODES.filter((item) => item.mode !== 'PREMIUM' || feature.premium_allowed).map((item) => (
                  <button
                    key={item.mode}
                    type="button"
                    role="radio"
                    aria-checked={feature.mode === item.mode}
                    disabled={busy !== null}
                    onClick={() => void change(feature, item.mode)}
                    className={`px-3 py-1.5 text-sm disabled:opacity-60 ${
                      feature.mode === item.mode
                        ? item.mode === 'OFF'
                          ? 'bg-app-danger/90 text-white'
                          : 'bg-app-button text-app-button-text'
                        : 'hover:bg-app-surface'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </Card>
      )}
    </>
  )
}
