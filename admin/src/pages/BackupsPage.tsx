import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, InlineError, PageHeader, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Backup, BackupStatus, BackupSummary } from '../types/api'
import { formatDateTime } from '../utils/format'

const KIND_LABELS: Record<string, string> = {
  DAILY: 'Kunlik',
  MONTHLY: 'Oylik',
  MANUAL: "Qo'lda",
}
const STATUS_TONE: Record<BackupStatus, 'success' | 'danger'> = { SUCCESS: 'success', FAILED: 'danger' }

function humanSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
}

export function BackupsPage() {
  const { api, download } = useSession()
  const { state, reload } = useAsync((signal) => api<BackupSummary>('/api/v1/admin/backups', { signal }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function takeNow() {
    setBusy(true)
    setError(null)
    try {
      await api('/api/v1/admin/backups', { method: 'POST' })
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Zaxira nusxa olib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function downloadBackup(backup: Backup) {
    setError(null)
    try {
      const blob = await download(`/api/v1/admin/backups/${backup.id}/download`)
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `kitobxon_${backup.created_at.slice(0, 10)}.dump`
      link.click()
      URL.revokeObjectURL(link.href)
    } catch {
      setError("Faylni yuklab bo'lmadi.")
    }
  }

  async function remove(backup: Backup) {
    if (!window.confirm(`Bu zaxira nusxani o'chirasizmi?\n\n${formatDateTime(backup.created_at)}`)) return
    setError(null)
    try {
      await api(`/api/v1/admin/backups/${backup.id}`, { method: 'DELETE' })
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "O'chirib bo'lmadi.")
    }
  }

  const summary = state.status === 'success' ? state.data : null
  return (
    <>
      <PageHeader
        title="Zaxira nusxa va tiklash"
        subtitle="Ma'lumotlar bazasining zaxira nusxalari (pg_dump). Faqat bosh administrator uchun."
        actions={
          <Button onClick={() => void takeNow()} loading={busy}>
            + Hozir zaxira olish
          </Button>
        }
      />
      <InlineError message={error} />

      {summary && (
        <Card className="mb-4 flex flex-col gap-2 p-4 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            {summary.enabled ? (
              <Badge tone="success">Avtomatik zaxira yoqilgan</Badge>
            ) : (
              <Badge tone="warning">Avtomatik zaxira o'chirilgan</Badge>
            )}
            <span className="text-app-hint">
              Har kecha soat 23:00 (Toshkent) da kunlik, oyning 1-sanasida oylik nusxa olinadi.
            </span>
          </div>
          <p className="text-app-hint">
            Saqlanadi: oxirgi {summary.retention_daily} ta kunlik, {summary.retention_monthly} ta oylik (qo'lda
            olinganlari saqlanib qoladi).
            {summary.last_success_at && <> Oxirgi muvaffaqiyatli nusxa: {formatDateTime(summary.last_success_at)}.</>}
          </p>
          <p className="text-app-hint">
            ⚠️ Bazani tiklash — bu yerda tugma orqali emas, server orqali bajariladigan ehtiyotkor amal.
            Tartib: <code>BACKUP_RESTORE_GUIDE_UZ.md</code> qo'llanmasida.
          </p>
        </Card>
      )}

      <Card>
        {state.status === 'loading' && <LoadingState />}
        {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
        {summary && (
          <Table head={['Sana', 'Turi', 'Hajmi', 'Holat', '']}>
            {summary.backups.length === 0 && <EmptyRow colSpan={5} text="Hali zaxira nusxa olinmagan" />}
            {summary.backups.map((backup) => (
              <tr key={backup.id}>
                <td className="whitespace-nowrap px-4 py-2.5">
                  {formatDateTime(backup.created_at)}
                  {backup.created_by_name && <p className="text-xs text-app-hint">{backup.created_by_name}</p>}
                </td>
                <td className="px-4 py-2.5">{KIND_LABELS[backup.kind] ?? backup.kind}</td>
                <td className="whitespace-nowrap px-4 py-2.5 tabular-nums">
                  {backup.status === 'SUCCESS' ? humanSize(backup.size_bytes) : '—'}
                </td>
                <td className="px-4 py-2.5">
                  <Badge tone={STATUS_TONE[backup.status]}>{backup.status === 'SUCCESS' ? 'Tayyor' : 'Xatolik'}</Badge>
                  {backup.status === 'FAILED' && backup.error && (
                    <p className="mt-1 max-w-sm text-xs text-app-hint">{backup.error}</p>
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  {backup.status === 'SUCCESS' && (
                    <Button variant="ghost" onClick={() => void downloadBackup(backup)}>
                      ⬇ Yuklab olish
                    </Button>
                  )}
                  <Button variant="ghost" className="text-app-danger" onClick={() => void remove(backup)}>
                    O'chirish
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </>
  )
}
