import { useState } from 'react'

import { Card, SectionTabs } from '../components/ui'
import { useSession } from '../store/session'
import { useRoute } from '../utils/router'
import { StarsOrdersPage } from './StarsOrdersPage'
import { SupportPage } from './SupportPage'

type Tab = 'tickets' | 'stars'

/** «📨 Murojaatlar»: a'zolarning botdagi murojaatlari va karta orqali olingan Stars buyurtmalari — bitta bo'limda.
 * Har bir ichki bo'lim o'z ruxsatiga qarab ko'rinadi (murojaatlar — SUPPORT_MANAGE, Stars — STARS_SEND). */
export function SupportHubPage() {
  const { can } = useSession()
  const route = useRoute()
  const tabs: { key: Tab; label: string }[] = []
  if (can('SUPPORT_MANAGE')) tabs.push({ key: 'tickets', label: '✉️ Murojaatlar' })
  if (can('STARS_SEND')) tabs.push({ key: 'stars', label: '⭐ Stars buyurtmalari' })

  const wantsStars = route.query.get('tab') === 'stars' && can('STARS_SEND')
  const [tab, setTab] = useState<Tab>(wantsStars ? 'stars' : (tabs[0]?.key ?? 'tickets'))

  if (tabs.length === 0) {
    return <Card className="p-6 text-sm text-app-hint">Bu bo'limni ko'rish uchun ruxsatingiz yo'q.</Card>
  }
  return (
    <div className="flex flex-col gap-4">
      {tabs.length > 1 && <SectionTabs tabs={tabs} active={tab} onChange={setTab} />}
      {tab === 'stars' ? <StarsOrdersPage /> : <SupportPage />}
    </div>
  )
}
