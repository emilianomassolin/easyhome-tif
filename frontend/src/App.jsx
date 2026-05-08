import { useState, useEffect, useCallback } from 'react'
import { getProperties } from './api'
import PropertyCard from './components/PropertyCard'
import PropertyModal from './components/PropertyModal'

const LIMIT = 20

export default function App() {
  const [props, setProps]           = useState([])
  const [total, setTotal]           = useState(0)
  const [skip, setSkip]             = useState(0)
  const [loading, setLoading]       = useState(true)
  const [selectedId, setSelectedId] = useState(null)

  const [fuente, setFuente]              = useState('')
  const [minScore, setMinScore]          = useState('')
  const [tipoOp, setTipoOp]              = useState('')
  const [soloAnalizados, setSoloAnalizados] = useState(false)

  const load = useCallback(async (newSkip = 0) => {
    setLoading(true)
    try {
      const data = await getProperties({ skip: newSkip, limit: LIMIT, fuente, min_score: minScore, tipo_operacion: tipoOp, solo_analizados: soloAnalizados })
      setProps(data.propiedades)
      setTotal(data.total)
      setSkip(newSkip)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [fuente, minScore, tipoOp, soloAnalizados])

  useEffect(() => { load(0) }, [load])

  const totalPages  = Math.ceil(total / LIMIT)
  const currentPage = Math.floor(skip / LIMIT) + 1

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">♿</span>
            <div>
              <h1 className="text-xl font-bold text-gray-900 leading-none">EasyHome</h1>
              <p className="text-xs text-gray-500">Viviendas accesibles en Mendoza</p>
            </div>
          </div>
          <span className="text-sm text-gray-500">{total.toLocaleString('es-AR')} propiedades</span>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Filtros */}
        <div className="bg-white rounded-2xl border border-gray-200 p-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-600">Operación</label>
              <div className="flex rounded-lg overflow-hidden border border-gray-200">
                {[['', 'Todas'], ['alquiler', 'Alquiler'], ['venta', 'Venta']].map(([val, label]) => (
                  <button
                    key={val}
                    onClick={() => setTipoOp(val)}
                    className={`px-3 py-2 text-sm font-medium transition-colors ${
                      tipoOp === val
                        ? 'bg-indigo-600 text-white'
                        : 'bg-white text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-600">Fuente</label>
              <select
                value={fuente}
                onChange={e => setFuente(e.target.value)}
                className="block border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300"
              >
                <option value="">Todas</option>
                <option value="mercadolibre">MercadoLibre</option>
                <option value="zonaprop">ZonaProp</option>
                <option value="mendozaprop">MendozaProp</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-600">Score mínimo</label>
              <select
                value={minScore}
                onChange={e => setMinScore(e.target.value)}
                className="block border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300"
              >
                <option value="">Todos</option>
                <option value="3">3+ Parcialmente accesible</option>
                <option value="5">5+ Accesible</option>
                <option value="7">7+ Muy accesible</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-600">Estado</label>
              <button
                onClick={() => setSoloAnalizados(v => !v)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  soloAnalizados
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                }`}
              >
                <span>{soloAnalizados ? '✓' : ''}</span>
                Solo analizados
              </button>
            </div>

            <button
              onClick={() => { setFuente(''); setMinScore(''); setTipoOp(''); setSoloAnalizados(false) }}
              className="text-sm text-gray-500 hover:text-gray-700 underline self-end pb-2"
            >
              Limpiar
            </button>
          </div>
        </div>

        {/* Grid */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="bg-white rounded-2xl border border-gray-200 h-72 animate-pulse" />
            ))}
          </div>
        ) : props.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <p className="text-4xl mb-3">🏠</p>
            <p>No se encontraron propiedades con esos filtros</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {props.map(p => (
              <PropertyCard key={p.id} prop={p} onClick={() => setSelectedId(p.id)} />
            ))}
          </div>
        )}

        {/* Paginación */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => load(skip - LIMIT)}
              disabled={skip === 0 || loading}
              className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-700 disabled:opacity-40 hover:bg-gray-50 transition-colors"
            >
              ← Anterior
            </button>
            <span className="text-sm text-gray-500">
              Página {currentPage} de {totalPages}
            </span>
            <button
              onClick={() => load(skip + LIMIT)}
              disabled={skip + LIMIT >= total || loading}
              className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-700 disabled:opacity-40 hover:bg-gray-50 transition-colors"
            >
              Siguiente →
            </button>
          </div>
        )}
      </div>

      {/* Modal */}
      {selectedId && (
        <PropertyModal id={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
