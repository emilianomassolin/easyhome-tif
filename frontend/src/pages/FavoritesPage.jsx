import { useState, useEffect } from 'react'
import { authApi } from '../authApi'
import { useAuth } from '../context/AuthContext'
import PropertyCard from '../components/PropertyCard'
import PropertyModal from '../components/PropertyModal'
import { SCORE_COLOR } from '../components/ScoreBar'

export default function FavoritesPage({ onClose }) {
  const { token, favoriteIds, toggleFavorite } = useAuth()
  const [favorites, setFavorites] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState(null)

  useEffect(() => {
    if (!token) return
    authApi.getFavorites(token)
      .then(res => setFavorites(res.favoritas || []))
      .finally(() => setLoading(false))
  }, [token])

  async function handleToggle(propertyId) {
    await toggleFavorite(propertyId)
    setFavorites(prev => prev.filter(p => p.id !== propertyId))
  }

  return (
    <div className="min-h-screen theme-bg">
      {/* Header */}
      <header className="sticky top-0 z-40"
        style={{
          background: 'var(--c-header)',
          backdropFilter: 'saturate(180%) blur(20px)',
          WebkitBackdropFilter: 'saturate(180%) blur(20px)',
          borderBottom: '1px solid var(--c-sep)',
        }}>
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <div>
            <h1 className="text-[17px] font-bold" style={{ color: 'var(--c-text)' }}>Mis favoritas</h1>
            {!loading && (
              <p className="text-[11px]" style={{ color: 'var(--c-text2)' }}>
                {favorites.length} propiedad{favorites.length !== 1 ? 'es' : ''} guardada{favorites.length !== 1 ? 's' : ''}
              </p>
            )}
          </div>
          <button onClick={onClose}
            className="px-4 py-2 rounded-xl text-sm font-semibold"
            style={{ backgroundColor: 'var(--c-surface2)', color: 'var(--c-text)', border: '1px solid var(--c-border)' }}>
            ← Volver
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-2xl animate-pulse" style={{ height: 280, backgroundColor: 'var(--c-surface3)' }} />
            ))}
          </div>
        ) : !favorites.length ? (
          <div className="text-center py-28 space-y-3">
            <p className="text-5xl">🤍</p>
            <p className="text-base font-semibold" style={{ color: 'var(--c-text)' }}>No tenés favoritas todavía</p>
            <p className="text-sm" style={{ color: 'var(--c-text3)' }}>Guardá propiedades tocando el corazón</p>
            <button onClick={onClose}
              className="mt-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white"
              style={{ backgroundColor: 'var(--c-blue)' }}>
              Explorar propiedades
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {favorites.map(p => (
              <div key={p.id} className="relative">
                {!p.activa && (
                  <div className="absolute inset-0 z-10 rounded-2xl flex items-center justify-center"
                    style={{ backgroundColor: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(3px)' }}>
                    <span className="text-xs font-semibold text-white bg-black/60 px-3 py-1.5 rounded-full">
                      No disponible
                    </span>
                  </div>
                )}
                <PropertyCard prop={p} onClick={() => setSelectedId(p.id)}
                  isFavorite={favoriteIds.has(p.id)}
                  onToggleFavorite={e => { e.stopPropagation(); handleToggle(p.id) }} />
              </div>
            ))}
          </div>
        )}
      </main>

      {selectedId && <PropertyModal id={selectedId} onClose={() => setSelectedId(null)} />}
    </div>
  )
}
