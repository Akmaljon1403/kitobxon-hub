
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
 * «Yuklab olish»: the bot sends the file to the member's chat, where Telegram keeps it and the phone can
 * save, print or forward it (the app itself stores nothing). Kept as one function for every document.
 */
export async function saveDocument(api: Api, ref: DocumentRef): Promise<'chat'> {
  await sendToChat(api, ref)
  return 'chat'
}
