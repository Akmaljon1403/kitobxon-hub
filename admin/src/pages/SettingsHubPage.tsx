import { useState } from 'react'

import { SectionTabs } from '../components/ui'
import { FacultiesPage } from './FacultiesPage'
import { SettingsPage } from './SettingsPage'

type Tab = 'settings' | 'faculties'

/** «⚙️ Sozlamalar»: the club's settings and the list of faculties, under one menu. */
export function SettingsHubPage() {
  const [tab, setTab] = useState<Tab>('settings')
  const tabs: { key: Tab; label: string }[] = [
    { key: 'settings', label: '⚙️ Sozlamalar' },
    { key: 'faculties', label: '🏛 Fakultetlar' },
  ]
  return (
    <div className="flex flex-col gap-4">
      <SectionTabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === 'settings' ? <SettingsPage /> : <FacultiesPage />}
    </div>
  )
}
