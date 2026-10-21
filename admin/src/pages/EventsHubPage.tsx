import { useState } from 'react'

import { Card, SectionTabs } from '../components/ui'
import { useSession } from '../store/session'
import { useRoute } from '../utils/router'
import { CampaignsPage } from './CampaignsPage'
import { EventsPage } from './EventsPage'

type Tab = 'events' | 'campaigns'

/** «📅 Tadbirlar»: tadbirlar/davomat va kitob tanlovlari — bitta bo'limda. Kitob tanlovi endi alohida
 * menyu emas, shu yerda: tadbirlar yonida yaratiladi va boshqariladi. Har qism o'z huquqiga qarab ko'rinadi
 * (tadbirlar — EVENT_VIEW, kitob tanlovlari — SEASON_MANAGE). */
export function EventsHubPage() {
  const { can } = useSession()
  const route = useRoute()
  const tabs: { key: Tab; label: string }[] = []
  if (can('EVENT_VIEW')) tabs.push({ key: 'events', label: '📅 Tadbirlar va davomat' })
  if (can('SEASON_MANAGE')) tabs.push({ key: 'campaigns', label: '📖 Kitob tanlovlari' })

  const wantsCampaigns = route.query.get('tab') === 'campaigns' && can('SEASON_MANAGE')
  const [tab, setTab] = useState<Tab>(wantsCampaigns ? 'campaigns' : (tabs[0]?.key ?? 'events'))

  if (tabs.length === 0) {
    return <Card className="p-6 text-sm text-app-hint">Bu bo'limni ko'rish uchun ruxsatingiz yo'q.</Card>
  }
  return (
    <div className="flex flex-col gap-4">
      {tabs.length > 1 && <SectionTabs tabs={tabs} active={tab} onChange={setTab} />}
      {tab === 'campaigns' ? <CampaignsPage /> : <EventsPage />}
    </div>
  )
}
