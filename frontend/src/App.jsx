import { useState, useEffect, useCallback } from 'react'
import { getProperties, getStats } from './api'
import PropertyCard from './components/PropertyCard'
import PropertyModal from './components/PropertyModal'
import AdminPanel from './pages/AdminPanel'
import { AuthProvider, useAuth } from './context/AuthContext'
import LoginModal from './components/LoginModal'
import ProfileModal from './components/ProfileModal'
import FavoritesPage from './pages/FavoritesPage'

const LIMIT = 20

const ZONAS_MENDOZA = [
  'Capital', 'Godoy Cruz', 'Las Heras', 'Guaymallén', 'Maipú',
  'Luján de Cuyo', 'San Rafael', 'Rivadavia', 'Junín', 'General Alvear',
  'San Martín', 'La Paz', 'Santa Rosa', 'Tunuyán', 'Tupungato',
  'San Carlos', 'Malargüe', 'Lavalle',
]

const TIPOS_PROPIEDAD = [
  { value: '', label: 'Todo tipo' },
  { value: 'departamento', label: 'Departamento' },
  { value: 'casa', label: 'Casa' },
  { value: 'ph', label: 'PH' },
  { value: 'oficina', label: 'Oficina' },
  { value: 'local', label: 'Local' },
  { value: 'terreno', label: 'Terreno' },
  { value: 'cochera', label: 'Cochera' },
]

const CRITERIOS_INFO = [
  { id: 'rampa',                    label: '♿ Rampa'         },
  { id: 'ascensor',                 label: '🛗 Ascensor'      },
  { id: 'bano_adaptado',            label: '🚿 Baño adaptado' },
  { id: 'entrada_ancha',            label: '🚪 Entrada ancha' },
  { id: 'estacionamiento_adaptado', label: '🅿️ PMD'           },
  { id: 'ducha_nivel_piso',         label: '🚿 Ducha italiana'},
  { id: 'pasamanos',                label: '🪜 Pasamanos'     },
  { id: 'planta_baja',              label: '🏠 Planta baja'   },
]

function DarkToggle({ dark, onToggle }) {
  return (
    <button
      onClick={onToggle}
      className="flex items-center gap-2 px-3 py-1.5 rounded-full transition-colors"
      style={{ backgroundColor: 'var(--c-surface2)', border: '1px solid var(--c-border)' }}
      title={dark ? 'Modo claro' : 'Modo oscuro'}
    >
      <span className="text-sm">{dark ? '☀️' : '🌙'}</span>
      <div
        className="relative w-9 h-5 rounded-full transition-colors duration-300"
        style={{ backgroundColor: dark ? 'var(--c-green)' : 'var(--c-surface3)' }}
      >
        <span
          className="absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-300"
          style={{ left: dark ? '18px' : '2px' }}
        />
      </div>
    </button>
  )
}

function Segmented({ options, value, onChange }) {
  return (
    <div className="flex rounded-xl p-0.5 gap-0.5" style={{ backgroundColor: 'var(--c-seg)' }}>
      {options.map(([val, label]) => (
        <button
          key={val}
          onClick={() => onChange(val)}
          className="px-3.5 py-1.5 rounded-[9px] text-xs font-semibold transition-all duration-150"
          style={value === val
            ? { backgroundColor: 'var(--c-seg-sel)', color: 'var(--c-text)', boxShadow: '0 1px 4px rgba(0,0,0,0.12)' }
            : { backgroundColor: 'transparent', color: 'var(--c-seg-txt)' }
          }
        >
          {label}
        </button>
      ))}
    </div>
  )
}

function AppContent() {
  const { user, token, favoriteIds, toggleFavorite } = useAuth()
  const [dark, setDark]               = useState(() => localStorage.getItem('eh-dark') === 'true')
  const [props, setProps]             = useState([])
  const [total, setTotal]             = useState(0)
  const [stats, setStats]             = useState({ total: 0, con_accesibilidad: 0 })
  const [skip, setSkip]               = useState(0)
  const [loading, setLoading]         = useState(true)
  const [selectedId, setSelectedId]   = useState(null)
  const [showAdmin, setShowAdmin]     = useState(false)
  const [showLogin, setShowLogin]     = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [showFavorites, setShowFavorites] = useState(false)

  const [fuente, setFuente]                 = useState('')
  const [minScore, setMinScore]             = useState('')
  const [tipoOp, setTipoOp]                 = useState('')
  const [soloAnalizados, setSoloAnalizados] = useState(false)
  const [zona, setZona]                     = useState('')
  const [tipoPropiedad, setTipoPropiedad]   = useState('')
  const [criterios, setCriterios]           = useState([])
  const [ordenScore, setOrdenScore]         = useState('desc')

  // Aplicar dark mode al <html>
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('eh-dark', dark)
  }, [dark])

  const toggleCriterio = id =>
    setCriterios(prev => prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id])

  const clearAll = () => {
    setFuente(''); setMinScore(''); setTipoOp(''); setSoloAnalizados(false)
    setZona(''); setTipoPropiedad(''); setCriterios([]); setOrdenScore('desc')
  }

  const load = useCallback(async (newSkip = 0) => {
    setLoading(true)
    try {
      const data = await getProperties({
        skip: newSkip, limit: LIMIT,
        fuente, min_score: minScore, tipo_operacion: tipoOp,
        solo_analizados: soloAnalizados,
        zona, tipo_propiedad: tipoPropiedad, criterios, orden: ordenScore,
      })
      setProps(data.propiedades)
      setTotal(data.total)
      setSkip(newSkip)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [fuente, minScore, tipoOp, soloAnalizados, zona, tipoPropiedad, criterios, ordenScore])

  useEffect(() => { load(0) }, [load])
  useEffect(() => { getStats().then(setStats).catch(() => {}) }, [])

  const totalPages  = Math.ceil(total / LIMIT)
  const currentPage = Math.floor(skip / LIMIT) + 1
  const hasFilters  = fuente || minScore || tipoOp || soloAnalizados || zona || tipoPropiedad || criterios.length > 0

  if (showAdmin) return <AdminPanel token={token} onClose={() => setShowAdmin(false)} />
  if (showFavorites) return <FavoritesPage onClose={() => setShowFavorites(false)} />

  return (
    <div className="min-h-screen theme-bg">

      {/* ── Header ── */}
      <header
        className="sticky top-0 z-40"
        style={{
          background: 'var(--c-header)',
          backdropFilter: 'saturate(180%) blur(20px)',
          WebkitBackdropFilter: 'saturate(180%) blur(20px)',
          borderBottom: '1px solid var(--c-sep)',
          transition: 'background 0.25s ease, border-color 0.25s ease',
        }}
      >
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-8 h-8 flex items-center justify-center rounded-[10px] shadow-sm"
              style={{ background: 'linear-gradient(145deg, #1C1C1E, #3A3A3C)' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M3 11L12 3l9 8v9a1 1 0 01-1 1H5a1 1 0 01-1-1v-9z" fill="white" fillOpacity="0.9"/>
                <rect x="9" y="14" width="6" height="7" rx="1" fill="#1C1C1E"/>
                <circle cx="17" cy="8" r="2.5" fill="#34C759"/>
              </svg>
            </div>
            <div>
              <h1 className="text-[17px] font-bold leading-none tracking-tight" style={{ color: 'var(--c-text)' }}>
                EasyHome
              </h1>
              <p className="text-[11px] mt-0.5" style={{ color: 'var(--c-text2)' }}>
                Viviendas accesibles · Mendoza
              </p>
            </div>
          </div>

          {/* Stats + toggle */}
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-5">
              <div className="text-right">
                <p className="text-lg font-bold tabular-nums leading-none" style={{ color: 'var(--c-text)' }}>
                  {stats.total.toLocaleString('es-AR')}
                </p>
                <p className="text-[11px] mt-0.5" style={{ color: 'var(--c-text2)' }}>propiedades</p>
              </div>
              <div style={{ width: 1, height: 28, backgroundColor: 'var(--c-border)' }} />
              <div className="text-right">
                <p className="text-lg font-bold tabular-nums leading-none" style={{ color: 'var(--c-green)' }}>
                  {stats.con_accesibilidad.toLocaleString('es-AR')}
                </p>
                <p className="text-[11px] mt-0.5" style={{ color: 'var(--c-text2)' }}>con accesibilidad</p>
              </div>
            </div>

            {user ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowFavorites(true)}
                  className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all"
                  style={{ backgroundColor: 'var(--c-surface2)', color: 'var(--c-text2)', border: '1px solid var(--c-border)' }}
                  title="Mis favoritas"
                >
                  ❤️ {favoriteIds.size > 0 ? favoriteIds.size : 'Favoritas'}
                </button>
                {user.is_admin && (
                  <button
                    onClick={() => setShowAdmin(true)}
                    className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all"
                    style={{ backgroundColor: 'var(--c-surface2)', color: 'var(--c-text2)', border: '1px solid var(--c-border)' }}
                    title="Panel de administración"
                  >
                    Admin
                  </button>
                )}
                <button
                  onClick={() => setShowProfile(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all"
                  style={{ backgroundColor: 'var(--c-blue)', color: '#fff' }}
                >
                  <span className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold"
                    style={{ backgroundColor: 'rgba(255,255,255,0.25)' }}>
                    {(user.nombre || user.email)[0].toUpperCase()}
                  </span>
                  {user.nombre || user.email.split('@')[0]}
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowLogin(true)}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all"
                style={{ backgroundColor: 'var(--c-blue)', color: '#fff' }}
              >
                Iniciar sesión
              </button>
            )}

            <DarkToggle dark={dark} onToggle={() => setDark(d => !d)} />
          </div>
        </div>
      </header>

      {/* ── Filtros ── */}
      <div
        className="sticky z-30"
        style={{
          top: 61,
          background: 'var(--c-filter)',
          backdropFilter: 'saturate(180%) blur(16px)',
          WebkitBackdropFilter: 'saturate(180%) blur(16px)',
          borderBottom: '1px solid var(--c-sep)',
          transition: 'background 0.25s ease',
        }}
      >
        <div className="max-w-7xl mx-auto px-6 py-3 space-y-2.5">

          {/* Fila 1 */}
          <div className="flex flex-wrap gap-2 items-center">
            <Segmented
              options={[['', 'Todos'], ['alquiler', 'Alquiler'], ['venta', 'Venta']]}
              value={tipoOp} onChange={setTipoOp}
            />

            {[
              { value: tipoPropiedad, onChange: setTipoPropiedad, options: TIPOS_PROPIEDAD.map(t => [t.value, t.label]) },
              { value: zona, onChange: setZona, options: [['', 'Todos los departamentos'], ...ZONAS_MENDOZA.map(z => [z, z])] },
              { value: fuente, onChange: setFuente, options: [['','Todas las fuentes'],['zonaprop','ZonaProp'],['mendozaprop','MendozaProp'],['argenprop','Argenprop']] },
              { value: minScore, onChange: setMinScore, options: [['','Cualquier score'],['3.5','Parcialmente accesible+'],['6','Accesible+'],['8.5','Muy accesible']] },
            ].map(({ value, onChange, options }, i) => (
              <select key={i} value={value} onChange={e => onChange(e.target.value)} className="apple-select">
                {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            ))}

            <Segmented
              options={[['desc', '↑ Score'], ['asc', '↓ Score']]}
              value={ordenScore} onChange={setOrdenScore}
            />

            <button
              onClick={() => setSoloAnalizados(v => !v)}
              className="px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all duration-150"
              style={soloAnalizados
                ? { backgroundColor: 'var(--c-blue)', color: '#FFFFFF' }
                : { backgroundColor: 'var(--c-input-bg)', color: 'var(--c-text2)', border: '1px solid var(--c-border)' }
              }
            >
              {soloAnalizados ? '✓ ' : ''}Analizados
            </button>

            {hasFilters && (
              <button onClick={clearAll} className="text-xs font-semibold ml-1" style={{ color: '#FF3B30' }}>
                Limpiar
              </button>
            )}
          </div>

          {/* Fila 2 — Criterios */}
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[11px] font-medium mr-1" style={{ color: 'var(--c-text3)' }}>Requiere:</span>
            {CRITERIOS_INFO.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => toggleCriterio(id)}
                className="px-3 py-1 rounded-full text-xs font-semibold transition-all duration-150"
                style={criterios.includes(id)
                  ? { backgroundColor: 'var(--c-blue)', color: '#FFFFFF' }
                  : { backgroundColor: 'var(--c-input-bg)', color: 'var(--c-text2)', border: '1px solid var(--c-border)' }
                }
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Contenido ── */}
      <div className="max-w-7xl mx-auto px-6 py-6 space-y-5">

        {!loading && (
          <p className="text-[13px]" style={{ color: 'var(--c-text3)' }}>
            <span className="font-semibold" style={{ color: 'var(--c-text2)' }}>
              {total.toLocaleString('es-AR')}
            </span> propiedades
            {currentPage > 1 && ` · página ${currentPage} de ${totalPages}`}
          </p>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="rounded-2xl animate-pulse" style={{ height: 280, backgroundColor: 'var(--c-surface3)' }} />
            ))}
          </div>
        ) : props.length === 0 ? (
          <div className="text-center py-28 space-y-3">
            <p className="text-5xl">🏠</p>
            <p className="text-base font-semibold" style={{ color: 'var(--c-text)' }}>Sin resultados</p>
            <p className="text-sm" style={{ color: 'var(--c-text3)' }}>Probá ajustando los filtros</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {props.map(p => (
              <PropertyCard
                key={p.id}
                prop={p}
                onClick={() => setSelectedId(p.id)}
                isFavorite={favoriteIds.has(p.id)}
                onToggleFavorite={user ? e => { e.stopPropagation(); toggleFavorite(p.id) } : e => { e.stopPropagation(); setShowLogin(true) }}
              />
            ))}
          </div>
        )}

        {/* Paginación */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => load(skip - LIMIT)}
              disabled={skip === 0 || loading}
              className="px-5 py-2 rounded-xl text-sm font-semibold disabled:opacity-30 transition-opacity"
              style={{ backgroundColor: 'var(--c-surface)', color: 'var(--c-blue)', border: '1px solid var(--c-border)' }}
            >← Anterior</button>
            <span className="text-sm font-medium tabular-nums" style={{ color: 'var(--c-text2)' }}>
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => load(skip + LIMIT)}
              disabled={skip + LIMIT >= total || loading}
              className="px-5 py-2 rounded-xl text-sm font-semibold disabled:opacity-30 transition-opacity"
              style={{ backgroundColor: 'var(--c-surface)', color: 'var(--c-blue)', border: '1px solid var(--c-border)' }}
            >Siguiente →</button>
          </div>
        )}
      </div>

      {selectedId && (
        <PropertyModal
          id={selectedId}
          onClose={() => setSelectedId(null)}
          onLoginRequired={() => { setSelectedId(null); setShowLogin(true) }}
        />
      )}
      {showLogin && <LoginModal onClose={() => setShowLogin(false)} />}
      {showProfile && <ProfileModal onClose={() => setShowProfile(false)} />}
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}
