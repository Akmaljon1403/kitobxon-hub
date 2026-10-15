import { useState } from 'react'

import { SectionTabs } from '../components/ui'
import { ContestsPage } from './ContestsPage'
import { GiveawaysPage } from './GiveawaysPage'

type Tab = 'giveaways' | 'contests'

/** «🎲 Sovg'a o'yinlari»: promo-code giveaways and the friend-invite contests, under one menu. */
export function GiveawaysHubPage() {
  const [tab, setTab] = useState<Tab>('giveaways')
  const tabs: { key: Tab; label: string }[] = [
    { key: 'giveaways', label: "🎲 Sovg'a o'yinlari" },
    { key: 'contests', label: '🏁 Taklif tanlovlari' },
  ]
  return (
    <div className="flex flex-col gap-4">
      <SectionTabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === 'giveaways' ? <GiveawaysPage /> : <ContestsPage />}
    </div>
  )
}
