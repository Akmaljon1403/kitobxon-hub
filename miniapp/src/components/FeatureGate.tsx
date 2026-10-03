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

/** Shows the page only when the member may use the feature. */
export function FeatureGate({ code, children }: { code: string; children: ReactNode }) {
  const access = useFeature(code)
  return access === 'on' ? <>{children}</> : <FeatureLocked code={code} access={access} />
}
