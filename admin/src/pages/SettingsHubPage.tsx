import { SectionTabs } from '../components/ui'
import { useSession } from '../store/session'
import { navigate, useRoute } from '../utils/router'
import { FacultiesPage } from './FacultiesPage'
import { SettingsPage } from './SettingsPage'
import { TextsPage } from './TextsPage'

type Tab = 'settings' | 'faculties' | 'texts'
const ROUTE = 'settings'

/** «⚙️ Sozlamalar»: klub sozlamalari, fakultetlar va bot/kanal matnlari — bitta bo'limda.
 * Faol qism havoladan (?tab=...) olinadi; matnlar «📝 Matnlar» huquqiga qarab ko'rinadi. */
export function SettingsHubPage() {
  const { can } = useSession()
  const route = useRoute()
  const tabs: { key: Tab; label: string }[] = [
    { key: 'settings', label: '⚙️ Sozlamalar' },
    { key: 'faculties', label: '🏛 Fakultetlar' },
  ]
  if (can('TEXTS_MANAGE')) tabs.push({ key: 'texts', label: '📝 Matnlar (bot va kanal)' })

  const active = tabs.find((t) => t.key === route.query.get('tab')) ?? tabs[0]
  return (
    <div className="flex flex-col gap-4">
      <SectionTabs tabs={tabs} active={active.key} onChange={(key) => navigate(`/${ROUTE}?tab=${key}`)} />
      {active.key === 'faculties' ? <FacultiesPage /> : active.key === 'texts' ? <TextsPage /> : <SettingsPage />}
    </div>
  )
}
