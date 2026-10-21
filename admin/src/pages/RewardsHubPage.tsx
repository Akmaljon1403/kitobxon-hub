import { Card, SectionTabs } from '../components/ui'
import { useSession } from '../store/session'
import { navigate, useRoute } from '../utils/router'
import { AchievementsPage } from './AchievementsPage'
import { ContestsPage } from './ContestsPage'
import { GiveawaysPage } from './GiveawaysPage'
import { MissionsPage } from './MissionsPage'
import { RewardsPage } from './RewardsPage'

type Tab = 'achievements' | 'rewards' | 'giveaways' | 'contests' | 'missions'
const ROUTE = 'rewards'

/** «🎁 Sovg'a va yutuqlar»: yutuqlar, sovg'alar, sovg'a o'yinlari, taklif tanlovlari va missiyalar — bitta
 * ixcham bo'limda. Har bir qism o'z huquqiga qarab ko'rinadi. Faol bo'lim havoladan (?tab=...) olinadi,
 * shuning uchun tashqi havolalar ham to'g'ri qismga ochadi. */
export function RewardsHubPage() {
  const { can } = useSession()
  const route = useRoute()

  const tabs: { key: Tab; label: string }[] = [{ key: 'achievements', label: '🏅 Yutuqlar' }]
  if (can('REWARD_MANAGE')) {
    tabs.push({ key: 'rewards', label: "🎁 Sovg'alar" })
    tabs.push({ key: 'giveaways', label: "🎲 Sovg'a o'yinlari" })
    tabs.push({ key: 'contests', label: '🏁 Taklif tanlovlari' })
  }
  if (can('SEASON_MANAGE')) tabs.push({ key: 'missions', label: '🎯 Missiyalar' })

  const active = tabs.find((t) => t.key === route.query.get('tab')) ?? tabs[0]
  if (!active) return <Card className="p-6 text-sm text-app-hint">Bu bo'limni ko'rish uchun ruxsatingiz yo'q.</Card>

  return (
    <div className="flex flex-col gap-4">
      {tabs.length > 1 && <SectionTabs tabs={tabs} active={active.key} onChange={(key) => navigate(`/${ROUTE}?tab=${key}`)} />}
      {active.key === 'rewards' ? (
        <RewardsPage />
      ) : active.key === 'giveaways' ? (
        <GiveawaysPage />
      ) : active.key === 'contests' ? (
        <ContestsPage />
      ) : active.key === 'missions' ? (
        <MissionsPage />
      ) : (
        <AchievementsPage />
      )}
    </div>
  )
}
