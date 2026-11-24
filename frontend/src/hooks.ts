import { useEffect, useState } from 'react'
import { api } from './api'

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (!path) return
    let aktif = true
    setLoading(true)
    setError(null)
    api<T>(path)
      .then((hasil) => {
        if (aktif) setData(hasil)
      })
      .catch((err: Error) => {
        if (aktif) setError(err.message)
      })
      .finally(() => {
        if (aktif) setLoading(false)
      })
    return () => {
      aktif = false
    }
  }, [path, nonce])

  return { data, loading, error, reload: () => setNonce((n) => n + 1) }
}
