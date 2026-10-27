import { useCallback } from 'react'

import { Icon, type IconName } from '../components/Icon'
import { Card, SectionTitle } from '../components/ui'
import { useBackButton } from '../hooks/useBackButton'
import { useAuth } from '../store/auth'
import { navigate } from '../utils/router'
import { selectionHaptic } from '../utils/telegram'

interface Service {
  route: string
  icon: IconName
  label: string
  /** Feature flag that gates this service; hidden when the flag is «off». */
  feature?: string
}

interface Group {
  title: string
  items: Service[]
}

// Every service that used to crowd the home screen, now grouped by what it is for.
const GROUPS: Group[] = [
  {
    title: 'Mutolaa',
    items: [
      { route: 'books', icon: 'book', label: 'Klub kitoblari' },
      { route: 'shelf', icon: 'bookmark', label: 'Javonim', feature: 'shelf' },
      { route: 'missions', icon: 'target', label: 'Missiyalar', feature: 'missions' },
      { route: 'quotes', icon: 'quote', label: 'Iqtiboslar sandig‘i', feature: 'quote_box' },
    ],
  },
  {
    title: 'Natija va reyting',
    items: [
      { route: 'results', icon: 'bar-chart', label: 'Natijalarim' },
      { route: 'stats', icon: 'bar-chart', label: 'Statistikam', feature: 'personal_stats' },
      { route: 'ranking', icon: 'trophy', label: 'Reyting', feature: 'ranking' },
      { route: 'league', icon: 'landmark', label: 'Fakultetlar ligasi', feature: 'faculty_league' },
      { route: 'achievements', icon: 'medal', label: 'Yutuqlar', feature: 'achievements' },
      { route: 'certificates', icon: 'graduation-cap', label: 'Sertifikatlar', feature: 'certificates' },
    ],
  },
  {
    title: 'Tadbirlar va hamjamiyat',
    items: [
      { route: 'events', icon: 'calendar', label: 'Tadbirlar' },
      { route: 'checkin', icon: 'check-circle', label: 'Davomat' },
      { route: 'tests', icon: 'file-text', label: 'Testlar' },
      { route: 'community', icon: 'users', label: 'A‘zolar fikrlari', feature: 'community' },
      { route: 'invite', icon: 'gift', label: 'Sizning foydangiz' },
    ],
  },
  {
    title: 'Kabinet',
    items: [
      { route: 'card', icon: 'id-card', label: 'Kitobxonlik kartam', feature: 'reading_card' },
      { route: 'rewards', icon: 'gift', label: 'Sovg‘alarim', feature: 'rewards' },
      { route: 'premium', icon: 'gem', label: 'Premium', feature: 'premium' },
      { route: 'help', icon: 'help-circle', label: 'Yordam va murojaat' },
    ],
  },
]

export function AllServicesPage() {
  const { me } = useAuth()
  const goBack = useCallback(() => navigate('/'), [])
  useBackButton(goBack)
  if (!me) return null

  const go = (route: string) => {
    selectionHaptic()
    navigate(`/${route}`)
  }

  return (
    <>
      <h1 className="px-1 pt-1 font-serif text-2xl font-bold">Barcha xizmatlar</h1>
      {GROUPS.map((group) => {
        const items = group.items.filter((item) => !item.feature || me.features?.[item.feature] !== 'off')
        if (items.length === 0) return null
        return (
          <div key={group.title} className="flex flex-col gap-1.5">
            <SectionTitle>{group.title}</SectionTitle>
            <Card className="flex flex-col divide-y divide-[color:var(--hairline)] p-0">
              {items.map((item) => {
                const premiumLocked = item.feature && item.feature !== 'premium' && me.features?.[item.feature] === 'premium'
                const trial = Boolean(item.feature && me.premium_trial && me.premium_features?.includes(item.feature))
                return (
                  <button
                    key={item.route}
                    type="button"
                    onClick={() => go(item.route)}
                    className="flex items-center gap-3 px-3.5 py-3 text-left transition-colors active:bg-app-surface"
                  >
                    <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-500/10 text-brand-600 dark:bg-white/10 dark:text-brand-300">
                      <Icon name={item.icon} size={20} />
                    </span>
                    <span className="flex-1 font-medium">{item.label}</span>
                    {(premiumLocked || trial) && (
                      <span
                        className="text-gold-500 dark:text-gold-300"
                        title={trial ? 'Premium — sinov davrida ochiq' : 'Premium'}
                        aria-label="Premium"
                      >
                        <Icon name="gem" size={16} />
                      </span>
                    )}
                    <Icon name="chevron-right" size={18} className="shrink-0 text-app-hint" />
                  </button>
                )
              })}
            </Card>
          </div>
        )
      })}
    </>
  )
}
