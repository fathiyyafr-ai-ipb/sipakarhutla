export class ApiError extends Error {
  status: number
  /** Isi mentah `detail` dari backend (bisa string, objek, atau daftar galat 422). */
  detail: unknown
  constructor(status: number, message: string, detail: unknown = undefined) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? ''

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  })
  if (res.status === 401 && !path.includes('/api/auth/')) {
    window.dispatchEvent(new Event('sipar-unauthorized'))
  }
  if (!res.ok) {
    let message = 'Terjadi kesalahan. Coba lagi.'
    let detail: unknown
    try {
      const body = await res.json()
      detail = body.detail
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      /* respons bukan JSON */
    }
    throw new ApiError(res.status, message, detail)
  }
  return (await res.json()) as T
}
