import { AppLayout } from './layouts/AppLayout'
import { AchievementsPage } from './pages/AchievementsPage'
import { FeatureGate } from './components/FeatureGate'
import { LoadingState } from './components/StateViews'
import { BookDetailPage } from './pages/BookDetailPage'
import { BooksPage } from './pages/BooksPage'
import { CertificatesPage } from './pages/CertificatesPage'
import { CheckInPage } from './pages/CheckInPage'
import { EventDetailPage } from './pages/EventDetailPage'
import { EventsPage } from './pages/EventsPage'
import { HelpPage } from './pages/HelpPage'
import { HomePage } from './pages/HomePage'
import { InvitePage } from './pages/InvitePage'
import { MissionsPage } from './pages/MissionsPage'
import { QuotesPage } from './pages/QuotesPage'
import { ReadingCardPage } from './pages/ReadingCardPage'
import { ShelfItemPage } from './pages/ShelfItemPage'
import { ShelfPage } from './pages/ShelfPage'
import { PremiumPage } from './pages/PremiumPage'
import { ProfilePage } from './pages/ProfilePage'
import { RankingPage } from './pages/RankingPage'
import { ResultsPage } from './pages/ResultsPage'
import { RewardsPage } from './pages/RewardsPage'
import { StatsPage } from './pages/StatsPage'
import { TestDetailPage } from './pages/TestDetailPage'
import { TestsPage } from './pages/TestsPage'
import {
  AccountProblemPage,
  NotFoundPage,
  NotRegisteredPage,
  OutsideTelegramPage,
  StartupErrorPage,
  SubscribePage,
} from './pages/StatusPages'
import { AuthProvider, useAuth } from './store/auth'
import { useRoute } from './utils/router'

function Routes() {
  const segments = useRoute()
  const [section = '', id] = segments
  let page
  if (section === '') page = <HomePage />
  else if (section === 'books' && id) page = <BookDetailPage bookId={id} />
  else if (section === 'books') page = <BooksPage />
  else if (section === 'events' && id) page = <EventDetailPage eventId={id} />
  else if (section === 'events') page = <EventsPage />
  else if (section === 'profile') page = <ProfilePage />
  else if (section === 'ranking') page = <FeatureGate code="ranking"><RankingPage /></FeatureGate>
  else if (section === 'results') page = <ResultsPage />
  else if (section === 'achievements') page = <FeatureGate code="achievements"><AchievementsPage /></FeatureGate>
  else if (section === 'rewards') page = <FeatureGate code="rewards"><RewardsPage /></FeatureGate>
  else if (section === 'tests' && id) page = <TestDetailPage testId={id} />
  else if (section === 'tests') page = <TestsPage />
  else if (section === 'checkin') page = <CheckInPage />
  else if (section === 'certificates') page = <FeatureGate code="certificates"><CertificatesPage certificateId={id} /></FeatureGate>
  else if (section === 'premium') page = <PremiumPage />
  else if (section === 'help') page = <HelpPage />
  else if (section === 'invite' || section === 'referal') page = <InvitePage />
  else if (section === 'shelf' && id) page = <FeatureGate code="shelf"><ShelfItemPage itemId={id} /></FeatureGate>
  else if (section === 'shelf') page = <FeatureGate code="shelf"><ShelfPage /></FeatureGate>
  else if (section === 'quotes') page = <FeatureGate code="quote_box"><QuotesPage /></FeatureGate>
  else if (section === 'missions') page = <FeatureGate code="missions"><MissionsPage /></FeatureGate>
  else if (section === 'card') page = <FeatureGate code="reading_card"><ReadingCardPage /></FeatureGate>
  else if (section === 'stats') page = <FeatureGate code="personal_stats"><StatsPage /></FeatureGate>
  else page = <NotFoundPage />
  return <AppLayout section={section}>{page}</AppLayout>
}

function Gate() {
  const { status } = useAuth()
  switch (status.kind) {
    case 'loading':
      return (
        <div className="flex min-h-screen items-center justify-center">
          <LoadingState label="Kitobxon Hub yuklanmoqda…" />
        </div>
      )
    case 'outside_telegram':
      return <OutsideTelegramPage />
    case 'not_registered':
      return <NotRegisteredPage />
    case 'blocked':
      return <AccountProblemPage message={status.message} />
    case 'subscribe':
      return <SubscribePage channels={status.channels} />
    case 'error':
      return <StartupErrorPage message={status.message} />
    case 'ready':
      return <Routes />
  }
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  )
}
