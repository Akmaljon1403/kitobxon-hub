import type { ReactNode } from 'react'

import { useAuth } from '../store/auth'
import type { FeatureAccess } from '../types/api'
import { navigate } from '../utils/router'
import { Button, Card } from './ui'

const TITLES: Record<string, string> = {
  passport: '🪪 Kitobxon pasporti',
  certificates: '🎓 Sertifikatlar',
  ranking: '🏆 Reyting',
  achievements: '🏅 Yutuqlar',
  rewards: "🎁 Sovg'alar",
  weekly_digest: '📊 Haftalik xulosa',
  personal_stats: '📈 Shaxsiy statistika',
  ranking_full: "🏆 To'liq reyting",
  certificate_pdf: '📄 Sertifikat PDF',
  portfolio: '🗂 Kitobxonlik portfoliosi',
}

export function useFeature(code: string): FeatureAccess {
  const { me } = useAuth()
  return me?.features?.[code] ?? 'on'
}

/** True while the member has Premium only thanks to the free trial and ``code`` is a Premium feature:
 * such places carry a 💎 mark, so the member knows what stays with Premium after the trial. */
export function useTrialMark(code: string): boolean {
  const { me } = useAuth()
  return Boolean(me?.premium_trial && me.premium_features?.includes(code))
}

/** The small «💎 Premium» mark shown during the trial. */
export function TrialBadge({ code, className = '' }: { code: string; className?: string }) {
  const marked = useTrialMark(code)
  if (!marked) return null
  return (
    <span
      title="Premium imkoniyat — sinov davrida ochiq"
      className={`inline-flex items-center gap-0.5 rounded-full bg-amber-400/20 px-1.5 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-300 ${className}`}
    >
      💎 Premium
    </span>
  )
}

/** A page placeholder for a feature that is switched off or reserved for Premium. */
export function FeatureLocked({ code, access }: { code: string; access: FeatureAccess }) {
  const title = TITLES[code] ?? 'Bu bo‘lim'
  if (access === 'premium') {
    return (
      <Card className="flex flex-col items-center gap-3 py-10 text-center">
        <span aria-hidden className="text-5xl">
          💎
        </span>
        <h1 className="text-lg font-semibold">«{title}» — Premium imkoniyat</h1>
        <p className="text-sm text-app-hint">Premium obuna bu va boshqa qo'shimcha imkoniyatlarni ochadi hamda klub rivojiga hissa bo'ladi.</p>
        <Button onClick={() => navigate('/premium')}>💎 Premium haqida</Button>
      </Card>
    )
  }
  return (
    <Card className="flex flex-col items-center gap-3 py-10 text-center">
      <span aria-hidden className="text-5xl">
        🔒
      </span>
      <h1 className="text-lg font-semibold">«{title}» hozircha o'chirilgan</h1>
      <p className="text-sm text-app-hint">Klub rahbariyati uni tez orada yoqishi mumkin.</p>
      <Button variant="secondary" onClick={() => navigate('/')}>
        🏠 Bosh sahifa
      </Button>
    </Card>
  )
}

/** Shows the page only when the member may use the feature (with a note during the Premium trial). */
export function FeatureGate({ code, children }: { code: string; children: ReactNode }) {
  const access = useFeature(code)
  const marked = useTrialMark(code)
  if (access !== 'on') return <FeatureLocked code={code} access={access} />
  return (
    <>
      {marked && (
        <p className="mb-2 rounded-xl bg-amber-400/15 px-3 py-2 text-xs text-app-text">
          💎 «{TITLES[code] ?? 'Bu bo‘lim'}» — Premium imkoniyat. Hozir sinov Premium'i tufayli ochiq.
        </p>
      )}
      {children}
    </>
  )
}
