import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, InlineError, Input, PageHeader, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Faculty } from '../types/api'

export function FacultiesPage() {
  const { api, can } = useSession()
  const canEdit = can('SETTINGS_MANAGE')
  const { state, reload } = useAsync((signal) => api<Faculty[]>('/api/v1/admin/faculties', { signal }))
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(false)
    }
  }

  const add = () =>
    run(async () => {
      const count = state.status === 'success' ? state.data.length : 0
      await api('/api/v1/admin/faculties', { method: 'POST', body: { name: name.trim(), sort_order: count + 1 } })
      setName('')
    })

  const rename = (faculty: Faculty) => {
    const value = window.prompt('Yangi nom:', faculty.name)
    if (value && value.trim() !== faculty.name) {
      void run(() => api(`/api/v1/admin/faculties/${faculty.id}`, { method: 'PATCH', body: { name: value.trim() } }))
    }
  }

  return (
    <>
      <PageHeader
        title="Fakultetlar"
        subtitle="Ro'yxatdan o'tishda a'zolar shu ro'yxatdan tanlaydi. Fakultetni o'chirib bo'lmaydi — faqat yashirish mumkin."
      />
      {canEdit && (
        <Card className="flex flex-wrap items-center gap-2 p-4">
          <Input
            value={name}
            maxLength={128}
            placeholder="Yangi fakultet nomi"
            onChange={(e) => setName(e.target.value)}
            className="max-w-sm"
          />
          <Button onClick={() => void add()} loading={busy} disabled={name.trim().length < 2}>
            Qo'shish
          </Button>
        </Card>
      )}
      <InlineError message={error} />
      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {state.status === 'success' && (
          <Table head={['Nomi', 'Holat', '']}>
            {state.data.length === 0 && <EmptyRow colSpan={3} text="Fakultetlar yo'q" />}
            {state.data.map((faculty) => (
              <tr key={faculty.id}>
                <td className="px-4 py-2.5 font-medium">{faculty.name}</td>
                <td className="px-4 py-2.5">
                  {faculty.is_active ? <Badge tone="success">Ko'rinadi</Badge> : <Badge>Yashirilgan</Badge>}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  {canEdit && (
                    <>
                      <Button variant="ghost" onClick={() => rename(faculty)}>
                        Nomini o'zgartirish
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() =>
                          void run(() =>
                            api(`/api/v1/admin/faculties/${faculty.id}`, {
                              method: 'PATCH',
                              body: { is_active: !faculty.is_active },
                            }),
                          )
                        }
                      >
                        {faculty.is_active ? 'Yashirish' : "Ko'rsatish"}
                      </Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </>
  )
}
