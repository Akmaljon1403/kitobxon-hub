import { LoadingState } from './components/StateViews'
import { Card } from './components/ui'
import { AdminLayout, NAV_ITEMS } from './layouts/AdminLayout'
import { AchievementsPage } from './pages/AchievementsPage'
import { AdminsPage } from './pages/AdminsPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { AttendancePage } from './pages/AttendancePage'
import { AuditPage } from './pages/AuditPage'
import { BooksPage } from './pages/BooksPage'
import { DashboardPage } from './pages/DashboardPage'
import { EventsPage } from './pages/EventsPage'
import { FacultiesPage } from './pages/FacultiesPage'
import { LoginPage } from './pages/LoginPage'
import { MembersPage } from './pages/MembersPage'
import { NotificationsPage } from './pages/NotificationsPage'
import { QuotesPage } from './pages/QuotesPage'
import { ReportEditorPage, ReportsPage } from './pages/ReportsPage'
import { RewardsPage } from './pages/RewardsPage'
import { ScoresPage } from './pages/ScoresPage'
import { SettingsPage } from './pages/SettingsPage'
import { SupportPage, SupportTicketPage } from './pages/SupportPage'
import { TestEditorPage } from './pages/TestEditorPage'
import { TestResultsPage } from './pages/TestResultsPage'
import { TestsPage } from './pages/TestsPage'
import { SessionProvider, useSession } from './store/session'
import { useRoute } from './utils/router'

const PAGES: Partial<Record<string, () => React.ReactElement>> = {
  '': DashboardPage,
  members: MembersPage,
  books: BooksPage,
  quotes: QuotesPage,
  events: EventsPage,
  tests: TestsPage,
  scores: ScoresPage,
  notifications: NotificationsPage,
  support: SupportPage,
  achievements: AchievementsPage,
  reports: ReportsPage,
  rewards: RewardsPage,
  analytics: AnalyticsPage,
  faculties: FacultiesPage,
  settings: SettingsPage,
  admins: AdminsPage,
  audit: AuditPage,
}

function Router() {
  const { state, admin, can } = useSession()
  const route = useRoute()
  const [section = ''] = route.segments

  if (section === 'login' && route.query.get('token')) {
    return <LoginPage linkToken={route.query.get('token')} />
  }
  if (state.kind === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState />
      </div>
    )
  }
  if (state.kind === 'signed_out') return <LoginPage linkToken={null} notice={state.message} />

  const [, entityId, subPage] = route.segments
  if (section === 'events' && entityId && subPage === 'attendance') {
    return (
      <AdminLayout section="events">
        {can('ATTENDANCE_VIEW') ? (
          <AttendancePage eventId={entityId} />
        ) : (
          <Card className="p-6 text-sm text-app-hint">Davomatni ko'rish uchun ruxsatingiz yo'q.</Card>
        )}
      </AdminLayout>
    )
  }

  if (section === 'support' && entityId) {
    return (
      <AdminLayout section="support">
        {can('SUPPORT_MANAGE') ? (
          <SupportTicketPage ticketId={entityId} />
        ) : (
          <Card className="p-6 text-sm text-app-hint">Murojaatlarni ko'rish uchun ruxsatingiz yo'q.</Card>
        )}
      </AdminLayout>
    )
  }

  if (section === 'reports' && entityId) {
    return (
      <AdminLayout section="reports">
        {can('REPORT_VIEW') ? (
          <ReportEditorPage reportId={entityId} />
        ) : (
          <Card className="p-6 text-sm text-app-hint">Hisobotlarni ko'rish uchun ruxsatingiz yo'q.</Card>
        )}
      </AdminLayout>
    )
  }

  if (section === 'tests' && entityId) {
    return (
      <AdminLayout section="tests">
        {!can('TEST_VIEW') ? (
          <Card className="p-6 text-sm text-app-hint">Testlarni ko'rish uchun ruxsatingiz yo'q.</Card>
        ) : subPage === 'results' ? (
          <TestResultsPage testId={entityId} />
        ) : (
          <TestEditorPage testId={entityId} />
        )}
      </AdminLayout>
    )
  }

  const item = NAV_ITEMS.find((nav) => nav.route === section)
  const Page = PAGES[section]
  const allowed = item?.visible(can, Boolean(admin?.is_super_admin)) ?? false
  return (
    <AdminLayout section={section === 'login' ? '' : section}>
      {section === 'login' ? (
        <DashboardPage />
      ) : Page && allowed ? (
        <Page />
      ) : (
        <Card className="p-6 text-sm text-app-hint">Bu sahifa mavjud emas yoki uni ko'rish uchun ruxsatingiz yo'q.</Card>
      )}
    </AdminLayout>
  )
}

export default function App() {
  return (
    <SessionProvider>
      <Router />
    </SessionProvider>
  )
}
