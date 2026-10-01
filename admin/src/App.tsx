import { LoadingState } from './components/StateViews'
import { Card } from './components/ui'
import { AdminLayout, NAV_ITEMS } from './layouts/AdminLayout'
import { AdminsPage } from './pages/AdminsPage'
import { AuditPage } from './pages/AuditPage'
import { BooksPage } from './pages/BooksPage'
import { DashboardPage } from './pages/DashboardPage'
import { FacultiesPage } from './pages/FacultiesPage'
import { LoginPage } from './pages/LoginPage'
import { MembersPage } from './pages/MembersPage'
import { QuotesPage } from './pages/QuotesPage'
import { SettingsPage } from './pages/SettingsPage'
import { SessionProvider, useSession } from './store/session'
import { useRoute } from './utils/router'

const PAGES: Partial<Record<string, () => React.ReactElement>> = {
  '': DashboardPage,
  members: MembersPage,
  books: BooksPage,
  quotes: QuotesPage,
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
