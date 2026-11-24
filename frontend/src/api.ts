export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
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
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      /* respons bukan JSON */
    }
    throw new ApiError(res.status, message)
  }
  return (await res.json()) as T
}
