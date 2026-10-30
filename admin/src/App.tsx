import { LoadingState } from './components/StateViews'
import { Card } from './components/ui'
import { AdminLayout, NAV_ITEMS } from './layouts/AdminLayout'
import { AdminsPage } from './pages/AdminsPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { AttendancePage } from './pages/AttendancePage'
import { AuditPage } from './pages/AuditPage'
import { BackupsPage } from './pages/BackupsPage'
import { BooksPage } from './pages/BooksPage'
import { CertificatesPage } from './pages/CertificatesPage'
import { CertificateDesignerPage } from './pages/CertificateDesignerPage'
import { DashboardPage } from './pages/DashboardPage'
import { EventsPage } from './pages/EventsPage'
import { ControlPage } from './pages/ControlPage'
import { LoginPage } from './pages/LoginPage'
import { MembersPage } from './pages/MembersPage'
import { MessagingPage } from './pages/MessagingPage'
import { CommunityHubPage } from './pages/CommunityHubPage'
import { RentalsPage } from './pages/RentalsPage'
import { RsvpPage } from './pages/RsvpPage'
import { PremiumHubPage } from './pages/PremiumHubPage'
import { DocumentsHubPage } from './pages/DocumentsHubPage'
import { ReportEditorPage } from './pages/ReportsPage'
import { RewardsHubPage } from './pages/RewardsHubPage'
import { ScoresPage } from './pages/ScoresPage'
import { SettingsHubPage } from './pages/SettingsHubPage'
import { SupportHubPage } from './pages/SupportHubPage'
import { SupportTicketPage } from './pages/SupportPage'
import { TestEditorPage } from './pages/TestEditorPage'
import { TestResultsPage } from './pages/TestResultsPage'
import { TestsPage } from './pages/TestsPage'
import { TrustPage } from './pages/TrustPage'
import { SessionProvider, useSession } from './store/session'
import { useRoute } from './utils/router'

const PAGES: Partial<Record<string, () => React.ReactElement>> = {
  '': DashboardPage,
  members: MembersPage,
  books: BooksPage,
  events: EventsPage,
  tests: TestsPage,
  scores: ScoresPage,
  notifications: MessagingPage,
  support: SupportHubPage,
  documents: DocumentsHubPage,
  rewards: RewardsHubPage,
  community: CommunityHubPage,
  rentals: RentalsPage,
  control: ControlPage,
  certificates: CertificatesPage,
  premium: PremiumHubPage,
  analytics: AnalyticsPage,
  settings: SettingsHubPage,
  admins: AdminsPage,
  backups: BackupsPage,
  audit: AuditPage,
  trust: TrustPage,
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
  if (section === 'events' && entityId && subPage === 'rsvp') {
    return (
      <AdminLayout section="events">
        {can('EVENT_VIEW') ? (
          <RsvpPage eventId={entityId} />
        ) : (
          <Card className="p-6 text-sm text-app-hint">Javoblarni ko'rish uchun ruxsatingiz yo'q.</Card>
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
      <AdminLayout section="documents">
        {can('REPORT_VIEW') ? (
          <ReportEditorPage reportId={entityId} />
        ) : (
          <Card className="p-6 text-sm text-app-hint">Hisobotlarni ko'rish uchun ruxsatingiz yo'q.</Card>
        )}
      </AdminLayout>
    )
  }

  if (section === 'certificates' && entityId) {
    return (
      <AdminLayout section="certificates">
        {can('REWARD_MANAGE') ? (
          <CertificateDesignerPage templateId={entityId} />
        ) : (
          <Card className="p-6 text-sm text-app-hint">Sertifikat dizaynlari uchun ruxsatingiz yo'q.</Card>
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
