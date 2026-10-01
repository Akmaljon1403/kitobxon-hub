import { useEffect, useRef, useState } from 'react'

import { LoadingState } from '../components/StateViews'
import { Card, InlineError } from '../components/ui'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import { navigate } from '../utils/router'

/** Login with the one-time link sent by the bot (#/login?token=...). */
export function LoginPage({ linkToken, notice }: { linkToken: string | null; notice?: string }) {
  const { loginWithLink } = useSession()
  const [error, setError] = useState<string | null>(null)
  const [working, setWorking] = useState(Boolean(linkToken))
  const started = useRef(false)

  useEffect(() => {
    if (!linkToken || started.current) return
    started.current = true
    loginWithLink(linkToken)
      .then(() => navigate('/'))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "Kirib bo'lmadi.")
        setWorking(false)
        // Remove the used token from the address bar.
        history.replaceState(null, '', `${location.pathname}#/login`)
      })
  }, [linkToken, loginWithLink])

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="flex w-full max-w-md flex-col gap-4 p-6">
        <div>
          <h1 className="text-xl font-semibold">📚 Kitobxon Hub</h1>
          <p className="text-sm text-app-hint">Admin panelga kirish</p>
        </div>
        {working ? (
          <LoadingState label="Kirilmoqda…" />
        ) : (
          <>
            <InlineError message={error ?? (notice || null)} />
            <ol className="list-decimal space-y-1.5 pl-5 text-sm">
              <li>Telegram'da klub botini oching.</li>
              <li>
                <code className="rounded bg-app-surface px-1.5 py-0.5">/admin</code> buyrug'ini yuboring.
              </li>
              <li>Bot yuborgan «🔐 Admin panelga kirish» tugmasini bosing.</li>
            </ol>
            <p className="text-xs text-app-hint">
              Havola faqat bir marta ishlaydi va 5 daqiqa amal qiladi. Parol kerak emas.
            </p>
          </>
        )}
      </Card>
    </main>
  )
}
