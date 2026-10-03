// Thin HTTP client for the Kitobxon Hub backend. All business rules live on the server;
// this module only sends requests and turns the server's error format into ApiError.

export interface ApiErrorBody {
  success: false
  error: { code: string; message: string; request_id?: string; details?: unknown }
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly requestId?: string

  constructor(code: string, message: string, status: number, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.requestId = requestId
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  token?: string | null
  signal?: AbortSignal
  idempotencyKey?: string
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.token) headers.Authorization = `Bearer ${options.token}`
  if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(
      'NETWORK_ERROR',
      "Internet aloqasi yo'q yoki server javob bermayapti. Aloqani tekshirib, qayta urinib ko'ring.",
      0,
    )
  }

  const requestId = response.headers.get('X-Request-ID') ?? undefined
  if (response.status === 204) return undefined as T

  let payload: unknown = null
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) {
    const body = payload as ApiErrorBody | null
    throw new ApiError(
      body?.error?.code ?? 'HTTP_ERROR',
      body?.error?.message ?? "So'rovni bajarib bo'lmadi. Keyinroq urinib ko'ring.",
      response.status,
      body?.error?.request_id ?? requestId,
    )
  }
  return payload as T
}

/** A file (image, PDF) from an authenticated endpoint. */
export async function apiBlob(path: string, token: string): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  } catch {
    throw new ApiError('NETWORK_ERROR', "Internet aloqasi yo'q. Qayta urinib ko'ring.", 0)
  }
  if (!response.ok) {
    let message = "Faylni yuklab bo'lmadi. Keyinroq urinib ko'ring."
    let code = 'HTTP_ERROR'
    try {
      const body = (await response.json()) as ApiErrorBody
      message = body.error?.message ?? message
      code = body.error?.code ?? code
    } catch {
      // not JSON
    }
    throw new ApiError(code, message, response.status)
  }
  return response.blob()
}

/** Upload a file (multipart) to an authenticated endpoint; answers 204 or JSON. */
export async function apiUpload(path: string, form: FormData, token: string, method: 'PUT' | 'POST' = 'PUT'): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { method, headers: { Authorization: `Bearer ${token}` }, body: form })
  } catch {
    throw new ApiError('NETWORK_ERROR', "Internet aloqasi yo'q. Qayta urinib ko'ring.", 0)
  }
  if (!response.ok) {
    let message = "Faylni yuklab bo'lmadi. Keyinroq urinib ko'ring."
    let code = 'HTTP_ERROR'
    try {
      const body = (await response.json()) as ApiErrorBody
      message = body.error?.message ?? message
      code = body.error?.code ?? code
    } catch {
      // not JSON
    }
    throw new ApiError(code, message, response.status)
  }
}
