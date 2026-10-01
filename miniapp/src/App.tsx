import { AppLayout } from './layouts/AppLayout'
import { LoadingState } from './components/StateViews'
import { BookDetailPage } from './pages/BookDetailPage'
import { BooksPage } from './pages/BooksPage'
import { EventDetailPage } from './pages/EventDetailPage'
import { EventsPage } from './pages/EventsPage'
import { HomePage } from './pages/HomePage'
import { ProfilePage } from './pages/ProfilePage'
import {
  AccountProblemPage,
  NotRegisteredPage,
  OutsideTelegramPage,
  StartupErrorPage,
  UpcomingPage,
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
  else page = <UpcomingPage section={section} />
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
