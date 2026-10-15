import { useState } from 'react'

import { SectionTabs } from '../components/ui'
import { useSession } from '../store/session'
import { useRoute } from '../utils/router'
import { DocumentsPage } from './DocumentsPage'
import { ReportsPage } from './ReportsPage'

type Tab = 'documents' | 'reports'

/** «🗂 Hujjatlar»: data exports (lists, statistics, attendance…) and the club's official reports. */
export function DocumentsHubPage() {
  const { can } = useSession()
  const route = useRoute()
  const showReports = can('REPORT_VIEW')
  const showDocuments =
    can('ANALYTICS_VIEW') || can('ATTENDANCE_VIEW') || can('TEST_VIEW') || can('USER_VIEW') || can('REPORT_VIEW')
  const [tab, setTab] = useState<Tab>(route.query.get('tab') === 'reports' && showReports ? 'reports' : 'documents')

  const tabs: { key: Tab; label: string }[] = []
  if (showDocuments) tabs.push({ key: 'documents', label: '🗂 Hujjatlar' })
  if (showReports) tabs.push({ key: 'reports', label: '📄 Rasmiy hisobotlar' })

  const active = tabs.some((item) => item.key === tab) ? tab : tabs[0]?.key

  return (
    <div className="flex flex-col gap-4">
      {tabs.length > 1 && <SectionTabs tabs={tabs} active={active ?? 'documents'} onChange={setTab} />}
      {active === 'reports' ? <ReportsPage /> : active === 'documents' ? <DocumentsPage /> : null}
    </div>
  )
}
