import { ApiError } from '../services/api'
import type { DownloadLink } from '../types/api'
import { getWebApp } from './telegram'

type Api = <T>(path: string, options?: { method?: 'POST'; body?: unknown }) => Promise<T>

export interface DocumentRef {
  kind: 'passport' | 'certificate' | 'portfolio'
  id?: string
}

function sendPath(ref: DocumentRef): string {
  if (ref.kind === 'passport') return '/api/v1/me/passport/send'
  if (ref.kind === 'portfolio') return '/api/v1/me/portfolio/send'
  return `/api/v1/me/certificates/${ref.id}/send`
}

/** The bot sends the file to the member's chat (works in every Telegram version). */
export async function sendToChat(api: Api, ref: DocumentRef): Promise<void> {
  await api(sendPath(ref), { method: 'POST' })
}

/**
 * Save a document: Telegram's own download dialog when available (Bot API 8.0+), otherwise the
 * bot sends the file to the chat. Returns how it was delivered, for the message shown to the member.
 */
export async function saveDocument(api: Api, ref: DocumentRef): Promise<'dialog' | 'chat'> {
  const webApp = getWebApp()
  if (webApp?.downloadFile && webApp.isVersionAtLeast('8.0')) {
    try {
      const link = await api<DownloadLink>('/api/v1/me/downloads', { method: 'POST', body: ref })
      const accepted = await new Promise<boolean>((resolve) =>
        webApp.downloadFile?.({ url: link.url, file_name: link.filename }, (ok) => resolve(ok)),
      )
      if (accepted) return 'dialog'
      throw new ApiError('CANCELLED', 'Yuklab olish bekor qilindi.', 0)
    } catch (error) {
      if (error instanceof ApiError && error.code === 'CANCELLED') throw error
      // No public link configured or an old client: fall back to the chat.
    }
  }
  await sendToChat(api, ref)
  return 'chat'
}
