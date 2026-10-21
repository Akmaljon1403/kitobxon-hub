import { SectionTabs } from '../components/ui'
import { navigate, useRoute } from '../utils/router'
import { FeaturesPage } from './FeaturesPage'
import { PremiumPage } from './PremiumPage'

type Tab = 'premium' | 'features'
const ROUTE = 'premium'

/** «💎 Premium va imkoniyatlar»: premium/to'lov sozlamalari va imkoniyatlar (feature-flaglar) — bitta
 * bo'limda (faqat bosh admin). Faol qism havoladan (?tab=...) olinadi. */
export function PremiumHubPage() {
  const route = useRoute()
  const tabs: { key: Tab; label: string }[] = [
    { key: 'premium', label: "💎 Premium va to'lovlar" },
    { key: 'features', label: '🧩 Imkoniyatlar' },
  ]
  const active = tabs.find((t) => t.key === route.query.get('tab')) ?? tabs[0]
  return (
    <div className="flex flex-col gap-4">
      <SectionTabs tabs={tabs} active={active.key} onChange={(key) => navigate(`/${ROUTE}?tab=${key}`)} />
      {active.key === 'features' ? <FeaturesPage /> : <PremiumPage />}
    </div>
  )
}
