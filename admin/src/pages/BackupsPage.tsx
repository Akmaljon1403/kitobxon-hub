import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, EmptyRow, InlineError, Input, Modal, PageHeader, Table, Textarea } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import type { Backup, BackupStatus, BackupSummary, GdriveTestResult, RestoreResult } from '../types/api'
import { formatDateTime } from '../utils/format'

const KIND_LABELS: Record<string, string> = {
  DAILY: 'Kunlik',
  MONTHLY: 'Oylik',
  MANUAL: "Qo'lda",
}
const STATUS_TONE: Record<BackupStatus, 'success' | 'danger'> = { SUCCESS: 'success', FAILED: 'danger' }
// The super admin must type this exact phrase to confirm a restore (mirrors the backend).
const RESTORE_PHRASE = 'TIKLASHNI TASDIQLAYMAN'

function humanSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
}

/** Google Drive off-site copy — configured by the super admin from the panel (no env editing). */
function GdriveConfig({ summary, reload }: { summary: BackupSummary; reload: () => void }) {
  const { api } = useSession()
  const [enabled, setEnabled] = useState(summary.gdrive_enabled)
  const [folderId, setFolderId] = useState(summary.gdrive_folder_id ?? '')
  const [serviceAccount, setServiceAccount] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setError(null)
    setNote(null)
    try {
      await api('/api/v1/admin/backups/gdrive', {
        method: 'POST',
        body: JSON.stringify({ enabled, folder_id: folderId.trim(), service_account: serviceAccount.trim() || null }),
      })
      setServiceAccount('')
      setNote('Saqlandi.')
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Saqlab bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function test() {
    setBusy(true)
    setError(null)
    setNote(null)
    try {
      const result = await api<GdriveTestResult>('/api/v1/admin/backups/gdrive/test', { method: 'POST' })
      if (result.ok) setNote(result.message)
      else setError(result.message)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Tekshirib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function clearConfig() {
    if (!window.confirm("Google Drive sozlamasini o'chirasizmi?")) return
    setBusy(true)
    setError(null)
    setNote(null)
    try {
      await api('/api/v1/admin/backups/gdrive', { method: 'DELETE' })
      setEnabled(false)
      setFolderId('')
      setServiceAccount('')
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "O'chirib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="mb-4 flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">☁️ Google Drive nusxa</h2>
        {summary.gdrive_configured ? <Badge tone="success">Sozlangan</Badge> : <Badge tone="neutral">Sozlanmagan</Badge>}
      </div>
      <p className="text-sm text-app-hint">
        Har bir zaxira qo'shimcha ravishda Google Drive'ga ham yuboriladi. Google Cloud'da «service account» yarating,
        Drive papkasini uning e-mailiga ulashing, so'ng papka ID va service account JSON faylini quyiga joylashtiring.
      </p>
      {summary.gdrive_source === 'env' && (
        <p className="text-xs text-app-hint">
          Hozir server sozlamasi (env) orqali ulangan. Bu yerda saqlasangiz, panel sozlamasi ustun bo'ladi.
        </p>
      )}
      <label className="flex items-center gap-2 text-sm font-medium">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Google Drive nusxa yoqilgan
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Drive papka ID</span>
        <Input value={folderId} onChange={(e) => setFolderId(e.target.value)} placeholder="masalan: 1A2b3C4d5E..." />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">
          Service account JSON{' '}
          {summary.gdrive_configured && <span className="font-normal text-app-hint">(saqlangan — o'zgartirish uchun yangisini joylang)</span>}
        </span>
        <Textarea
          value={serviceAccount}
          onChange={(e) => setServiceAccount(e.target.value)}
          rows={4}
          placeholder={summary.gdrive_configured ? "•••••• (saqlangan — ko'rsatilmaydi)" : '{ "type": "service_account", ... }'}
        />
      </label>
      {error && <p className="text-sm text-app-danger">{error}</p>}
      {note && !error && <p className="text-sm text-emerald-600 dark:text-emerald-400">{note}</p>}
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void save()} loading={busy}>
          Saqlash
        </Button>
        <Button variant="secondary" onClick={() => void test()} loading={busy} disabled={!summary.gdrive_configured}>
          Ulanishni tekshirish
        </Button>
        {summary.gdrive_configured && (
          <Button variant="ghost" className="text-app-danger" onClick={() => void clearConfig()}>
            O'chirish
          </Button>
        )}
      </div>
    </Card>
  )
}

export function BackupsPage() {
  const { api, download } = useSession()
  const { state, reload } = useAsync((signal) => api<BackupSummary>('/api/v1/admin/backups', { signal }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Restore dialog
  const [restoreTarget, setRestoreTarget] = useState<Backup | null>(null)
  const [confirmText, setConfirmText] = useState('')
  const [restoreLive, setRestoreLive] = useState(false)
  const [restoreBusy, setRestoreBusy] = useState(false)
  const [restoreError, setRestoreError] = useState<string | null>(null)
  const [restoreResult, setRestoreResult] = useState<RestoreResult | null>(null)

  function openRestore(backup: Backup) {
    setRestoreTarget(backup)
    setConfirmText('')
    setRestoreLive(false)
    setRestoreError(null)
    setRestoreResult(null)
  }

  async function doRestore() {
    if (!restoreTarget) return
    setRestoreBusy(true)
    setRestoreError(null)
    try {
      const result = await api<RestoreResult>(`/api/v1/admin/backups/${restoreTarget.id}/restore`, {
        method: 'POST',
        body: JSON.stringify({ confirm: confirmText.trim(), live: restoreLive }),
      })
      setRestoreResult(result)
      reload() // the pre-restore safety backup now shows in the list
    } catch (err) {
      setRestoreError(err instanceof ApiError ? err.message : "Tiklab bo'lmadi.")
    } finally {
      setRestoreBusy(false)
    }
  }

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
            {summary.encryption_enabled ? (
              <Badge tone="success">🔒 Shifrlash yoqilgan</Badge>
            ) : (
              <Badge tone="neutral">Shifrlash o'chirilgan</Badge>
            )}
            {summary.gdrive_enabled && <Badge tone="success">☁️ Google Drive nusxa</Badge>}
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
            ♻️ <b>Tiklash</b> — har bir nusxa yonidagi «Tiklash» tugmasi orqali. Tugma avval zaxirani
            tekshiradi va <b>tiklashdan oldingi xavfsizlik nusxasini</b> oladi.{' '}
            {summary.restore_live_enabled ? (
              <span className="text-app-danger">Jonli bazani almashtirish YOQILGAN — ehtiyot bo'ling.</span>
            ) : (
              <>Jonli bazani almashtirish xavfsizlik uchun o'chirilgan (<code>ALLOW_IN_APP_RESTORE</code>).</>
            )}{' '}
            Batafsil: <code>BACKUP_RESTORE_GUIDE_UZ.md</code>.
          </p>
        </Card>
      )}

      {summary && <GdriveConfig summary={summary} reload={reload} />}

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
                  {backup.encrypted && <span title="Shifrlangan"> 🔒</span>}
                  {backup.in_drive && <span title="Google Drive'da nusxasi bor"> ☁️</span>}
                </td>
                <td className="px-4 py-2.5">
                  <Badge tone={STATUS_TONE[backup.status]}>{backup.status === 'SUCCESS' ? 'Tayyor' : 'Xatolik'}</Badge>
                  {backup.status === 'FAILED' && backup.error && (
                    <p className="mt-1 max-w-sm text-xs text-app-hint">{backup.error}</p>
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-right">
                  {backup.status === 'SUCCESS' && (
                    <>
                      <Button variant="ghost" onClick={() => void downloadBackup(backup)}>
                        ⬇ Yuklab olish
                      </Button>
                      <Button variant="ghost" onClick={() => openRestore(backup)}>
                        ♻️ Tiklash
                      </Button>
                    </>
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

      {restoreTarget && (
        <Modal
          title="Zaxiradan tiklash"
          onClose={() => setRestoreTarget(null)}
          footer={
            restoreResult ? (
              <Button onClick={() => setRestoreTarget(null)}>Yopish</Button>
            ) : (
              <>
                <Button variant="secondary" onClick={() => setRestoreTarget(null)}>
                  Bekor qilish
                </Button>
                <Button
                  className={restoreLive ? 'bg-app-danger' : ''}
                  loading={restoreBusy}
                  disabled={confirmText.trim() !== RESTORE_PHRASE}
                  onClick={() => void doRestore()}
                >
                  {restoreLive ? 'Jonli bazani tiklash' : 'Tekshirish + xavfsizlik nusxasi'}
                </Button>
              </>
            )
          }
        >
          {restoreResult ? (
            <div className="flex flex-col gap-2 text-sm">
              <p className={restoreResult.live_restored ? 'font-semibold text-emerald-600 dark:text-emerald-400' : ''}>
                {restoreResult.message}
              </p>
              <p className="text-app-hint">Tekshirilgan yozuvlar: {restoreResult.entries} ta.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3 text-sm">
              <p>
                Tanlangan nusxa: <b>{formatDateTime(restoreTarget.created_at)}</b>{' '}
                ({KIND_LABELS[restoreTarget.kind] ?? restoreTarget.kind}).
              </p>
              <p className="text-app-hint">
                Tiklashdan oldin tizim avtomatik ravishda hozirgi holatning <b>xavfsizlik nusxasini</b> oladi va
                zaxira faylini tekshiradi. Shundan keyingina {restoreLive ? 'jonli baza almashtiriladi' : 'natija ko‘rsatiladi'}.
              </p>
              {summary?.restore_live_enabled ? (
                <label className="flex items-start gap-2 rounded-lg bg-app-danger/10 p-3">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={restoreLive}
                    onChange={(e) => setRestoreLive(e.target.checked)}
                  />
                  <span>
                    <b className="text-app-danger">Jonli bazani almashtirish.</b> Hozirgi barcha ma'lumotlar ushbu
                    zaxiradagi holat bilan almashtiriladi. Tiklashdan so'ng ilovani qayta ishga tushiring.
                  </span>
                </label>
              ) : (
                <p className="rounded-lg bg-app-muted/40 p-3 text-app-hint">
                  Jonli bazani almashtirish bu serverda o'chirilgan (<code>ALLOW_IN_APP_RESTORE</code>). Tugma faqat
                  tekshiradi va xavfsizlik nusxasini oladi.
                </p>
              )}
              <div>
                <p className="mb-1">
                  Tasdiqlash uchun <b>{RESTORE_PHRASE}</b> deb yozing:
                </p>
                <Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} placeholder={RESTORE_PHRASE} />
              </div>
              <InlineError message={restoreError} />
            </div>
          )}
        </Modal>
      )}
    </>
  )
}
