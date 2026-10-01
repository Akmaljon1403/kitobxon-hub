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
  const isForm = options.body instanceof FormData
  if (options.body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  if (options.token) headers.Authorization = `Bearer ${options.token}`
  if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : isForm ? (options.body as FormData) : JSON.stringify(options.body),
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

/** Downloads a protected file (PDF, CSV, image) with the admin token. */
export async function fetchBlob(path: string, token: string | null): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!response.ok) {
    let message = "Faylni yuklab bo'lmadi."
    try {
      const body = (await response.json()) as ApiErrorBody
      message = body.error?.message ?? message
    } catch {
      // not JSON
    }
    throw new ApiError('DOWNLOAD_FAILED', message, response.status)
  }
  return response.blob()
}

export function saveBlob(blob: Blob, filename: string): void {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
}
