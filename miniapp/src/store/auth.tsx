import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { ApiError, apiBlob, apiRequest, apiUpload, type RequestOptions } from '../services/api'
import type { Me, PublicMeta, SubscriptionChannel, TokenResponse } from '../types/api'
import { getWebApp } from '../utils/telegram'

type AuthStatus =
  | { kind: 'loading' }
  | { kind: 'ready' }
  | { kind: 'outside_telegram' }
  | { kind: 'not_registered' }
  | { kind: 'blocked'; message: string }
  | { kind: 'subscribe'; channels: SubscriptionChannel[] }
  | { kind: 'error'; message: string }

interface AuthContextValue {
  status: AuthStatus
  me: Me | null
  meta: PublicMeta | null
  /** Authenticated API call; re-authenticates once with Telegram data when the token expired. */
  api: <T>(path: string, options?: Omit<RequestOptions, 'token'>) => Promise<T>
  /** Authenticated file download (images, PDFs). */
  download: (path: string) => Promise<Blob>
  /** Authenticated file upload (multipart). */
  upload: (path: string, form: FormData, method?: 'PUT' | 'POST') => Promise<void>
  refreshMe: () => Promise<void>
  retry: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)
const TOKEN_KEY = 'kitobxon.member.token'

function storedToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function storeToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage can be unavailable in some webviews; the token then lives in memory only.
  }
}

const ACCOUNT_ERRORS = new Set(['USER_BLOCKED', 'USER_PENDING', 'USER_INACTIVE', 'LICENCE_EXPIRED'])

function channelsOf(error: ApiError): SubscriptionChannel[] {
  const details = error.details as { channels?: SubscriptionChannel[] } | undefined
  return Array.isArray(details?.channels) ? details.channels : []
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>({ kind: 'loading' })
  const [me, setMe] = useState<Me | null>(null)
  const [meta, setMeta] = useState<PublicMeta | null>(null)
  const [attempt, setAttempt] = useState(0)
  const tokenRef = useRef<string | null>(storedToken())

  const signIn = useCallback(async (): Promise<string> => {
    const webApp = getWebApp()
    if (!webApp) throw new ApiError('OUTSIDE_TELEGRAM', 'Ilovani Telegram orqali oching.', 0)
    const result = await apiRequest<TokenResponse>('/api/v1/auth/telegram', {
      method: 'POST',
      body: { init_data: webApp.initData },
    })
    tokenRef.current = result.access_token
    storeToken(result.access_token)
    return result.access_token
  }, [])

  const api = useCallback(
    async <T,>(path: string, options: Omit<RequestOptions, 'token'> = {}): Promise<T> => {
      const token = tokenRef.current ?? (await signIn())
      try {
        return await apiRequest<T>(path, { ...options, token })
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          const fresh = await signIn()
          return apiRequest<T>(path, { ...options, token: fresh })
        }
        // Left the club channel while the app was open: show the «subscribe» screen.
        if (error instanceof ApiError && error.code === 'SUBSCRIPTION_REQUIRED')
          setStatus({ kind: 'subscribe', channels: channelsOf(error) })
        // A rented copy whose licence ended while the app was open.
        if (error instanceof ApiError && error.code === 'LICENCE_EXPIRED') setStatus({ kind: 'blocked', message: error.message })
        throw error
      }
    },
    [signIn],
  )

  const download = useCallback(
    async (path: string): Promise<Blob> => {
      const token = tokenRef.current ?? (await signIn())
      try {
        return await apiBlob(path, token)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return apiBlob(path, await signIn())
        throw error
      }
    },
    [signIn],
  )

  const upload = useCallback(
    async (path: string, form: FormData, method: 'PUT' | 'POST' = 'PUT'): Promise<void> => {
      const token = tokenRef.current ?? (await signIn())
      try {
        await apiUpload(path, form, token, method)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return apiUpload(path, form, await signIn(), method)
        throw error
      }
    },
    [signIn],
  )

  const refreshMe = useCallback(async () => {
    setMe(await api<Me>('/api/v1/me'))
  }, [api])

  useEffect(() => {
    let cancelled = false
    async function start() {
      setStatus({ kind: 'loading' })
      apiRequest<PublicMeta>('/api/v1/meta').then(setMeta).catch(() => undefined)
      if (!getWebApp()) {
        setStatus({ kind: 'outside_telegram' })
        return
      }
      try {
        tokenRef.current = null
        await signIn()
        const profile = await api<Me>('/api/v1/me')
        if (cancelled) return
        setMe(profile)
        if (profile.subscription_missing?.length) setStatus({ kind: 'subscribe', channels: profile.subscription_missing })
        else setStatus({ kind: 'ready' })
      } catch (error) {
        if (cancelled) return
        if (error instanceof ApiError && error.code === 'USER_NOT_REGISTERED') setStatus({ kind: 'not_registered' })
        else if (error instanceof ApiError && ACCOUNT_ERRORS.has(error.code))
          setStatus({ kind: 'blocked', message: error.message })
        else
          setStatus({
            kind: 'error',
            message: error instanceof ApiError ? error.message : "Kutilmagan xatolik yuz berdi.",
          })
      }
    }
    void start()
    return () => {
      cancelled = true
    }
  }, [api, signIn, attempt])

  const value = useMemo<AuthContextValue>(
    () => ({ status, me, meta, api, download, upload, refreshMe, retry: () => setAttempt((n) => n + 1) }),
    [status, me, meta, api, download, upload, refreshMe],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
