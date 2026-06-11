import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authApi } from '../authApi'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem('eh-auth-token'))
  const [loading, setLoading] = useState(() => !!localStorage.getItem('eh-auth-token'))
  const [favoriteIds, setFavoriteIds] = useState(new Set())

  useEffect(() => {
    const stored = localStorage.getItem('eh-auth-token')
    if (!stored) return
    authApi.me(stored)
      .then(u => {
        setUser(u)
        return authApi.getFavoriteIds(stored)
      })
      .then(ids => setFavoriteIds(new Set(ids)))
      .catch(() => {
        localStorage.removeItem('eh-auth-token')
        setToken(null)
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  function login(newToken, newUser) {
    localStorage.setItem('eh-auth-token', newToken)
    setToken(newToken)
    setUser(newUser)
    authApi.getFavoriteIds(newToken)
      .then(ids => setFavoriteIds(new Set(ids)))
      .catch(() => {})
  }

  function logout() {
    localStorage.removeItem('eh-auth-token')
    setToken(null)
    setUser(null)
    setFavoriteIds(new Set())
  }

  const toggleFavorite = useCallback(async (propertyId) => {
    if (!token) return false
    const isFav = favoriteIds.has(propertyId)
    try {
      if (isFav) {
        await authApi.removeFavorite(token, propertyId)
        setFavoriteIds(prev => { const s = new Set(prev); s.delete(propertyId); return s })
      } else {
        await authApi.addFavorite(token, propertyId)
        setFavoriteIds(prev => new Set([...prev, propertyId]))
      }
      return true
    } catch {
      return false
    }
  }, [token, favoriteIds])

  return (
    <AuthContext.Provider value={{ user, token, loading, favoriteIds, login, logout, toggleFavorite }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- contexto y hook van juntos
export const useAuth = () => useContext(AuthContext)
