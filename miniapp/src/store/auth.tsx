import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { ApiError, apiRequest, type RequestOptions } from '../services/api'
import type { Me, PublicMeta, TokenResponse } from '../types/api'
import { getWebApp } from '../utils/telegram'

type AuthStatus =
  | { kind: 'loading' }
  | { kind: 'ready' }
  | { kind: 'outside_telegram' }
  | { kind: 'not_registered' }
  | { kind: 'blocked'; message: string }
  | { kind: 'error'; message: string }

interface AuthContextValue {
  status: AuthStatus
  me: Me | null
  meta: PublicMeta | null
  /** Authenticated API call; re-authenticates once with Telegram data when the token expired. */
  api: <T>(path: string, options?: Omit<RequestOptions, 'token'>) => Promise<T>
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

const ACCOUNT_ERRORS = new Set(['USER_BLOCKED', 'USER_PENDING', 'USER_INACTIVE'])

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
        setStatus({ kind: 'ready' })
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
    () => ({ status, me, meta, api, refreshMe, retry: () => setAttempt((n) => n + 1) }),
    [status, me, meta, api, refreshMe],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
