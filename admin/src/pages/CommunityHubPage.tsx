import { useState } from 'react'

import { SectionTabs } from '../components/ui'
import { useSession } from '../store/session'
import { CommunityPage } from './CommunityPage'
import { QuotesPage } from './QuotesPage'

type Tab = 'feedback' | 'quotes'

/** «💬 A'zolar fikrlari»: members' contributions and the club's own book quotes, under one menu. */
export function CommunityHubPage() {
  const { can } = useSession()
  const showFeedback = can('COMMUNITY_MANAGE')
  const showQuotes = can('BOOK_VIEW')
  const [tab, setTab] = useState<Tab>(showFeedback ? 'feedback' : 'quotes')

  const tabs: { key: Tab; label: string }[] = []
  if (showFeedback) tabs.push({ key: 'feedback', label: '👥 A’zolar fikrlari' })
  if (showQuotes) tabs.push({ key: 'quotes', label: '📖 Kitob iqtiboslari' })

  const active = tabs.some((item) => item.key === tab) ? tab : tabs[0]?.key

  return (
    <div className="flex flex-col gap-4">
      {tabs.length > 1 && <SectionTabs tabs={tabs} active={active ?? 'feedback'} onChange={setTab} />}
      {active === 'feedback' ? <CommunityPage /> : active === 'quotes' ? <QuotesPage /> : null}
    </div>
  )
}
