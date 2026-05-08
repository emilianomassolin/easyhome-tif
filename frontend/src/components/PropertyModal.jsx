import { useState, useEffect, useRef } from 'react'
import { getProperty, analyzeProperty } from '../api'
import ScoreBar from './ScoreBar'

const CRITERIOS_LABEL = {
  rampa:                    '♿ Rampa de acceso',
  ascensor:                 '🛗 Ascensor',
  bano_adaptado:            '🚿 Baño adaptado',
  entrada_ancha:            '🚪 Entrada ancha',
  sin_escalones:            '✅ Sin escalones',
  piso_plano:               '📐 Piso plano',
  estacionamiento_adaptado: '🅿️ Estacionamiento PMD',
}

export default function PropertyModal({ id, onClose }) {
  const [prop, setProp]           = useState(null)
  const [loading, setLoading]     = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError]         = useState(null)
  const [fotoIdx, setFotoIdx]     = useState(0)

  useEffect(() => {
    getProperty(id)
      .then(setProp)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  async function handleAnalyze() {
    setAnalyzing(true)
    try {
      const result = await analyzeProperty(id)
      setProp(prev => ({
        ...prev,
        score_accesibilidad: result.score_accesibilidad,
        nivel_accesibilidad: result.nivel,
        justificacion_score: result.justificacion,
        criterios_detectados: result.criterios_detectados,
        analizado: true,
      }))
    } catch (e) {
      setError(e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {loading && (
          <div className="p-8 text-center text-gray-500">Cargando...</div>
        )}

        {error && (
          <div className="p-8 text-center text-red-500">{error}</div>
        )}

        {prop && !loading && (
          <>
            {/* Galería */}
            {prop.fotos_urls?.length > 0 && (
              <div className="relative h-56 bg-gray-100 overflow-hidden group">
                <img
                  src={prop.fotos_urls[fotoIdx]}
                  alt={prop.titulo}
                  className="w-full h-full object-cover"
                />
                {prop.fotos_urls.length > 1 && (
                  <>
                    <button
                      onClick={() => setFotoIdx(i => (i - 1 + prop.fotos_urls.length) % prop.fotos_urls.length)}
                      className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white rounded-full w-8 h-8 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >‹</button>
                    <button
                      onClick={() => setFotoIdx(i => (i + 1) % prop.fotos_urls.length)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white rounded-full w-8 h-8 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >›</button>
                    <span className="absolute bottom-2 right-3 text-xs text-white bg-black/40 px-2 py-0.5 rounded-full">
                      {fotoIdx + 1}/{prop.fotos_urls.length}
                    </span>
                  </>
                )}
              </div>
            )}

            <div className="p-6 space-y-5">
              {/* Header */}
              <div className="flex items-start justify-between gap-4">
                <h2 className="text-lg font-bold text-gray-900 leading-snug">{prop.titulo}</h2>
                <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl shrink-0">✕</button>
              </div>

              {prop.ubicacion && (
                <p className="text-sm text-gray-500">📍 {prop.ubicacion}</p>
              )}

              {prop.precio && (
                <p className="text-2xl font-bold text-gray-900">${prop.precio.toLocaleString('es-AR')}</p>
              )}

              {/* Score */}
              <div className="bg-gray-50 rounded-xl p-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-700">Accesibilidad</h3>
                <ScoreBar score={prop.score_accesibilidad} nivel={prop.nivel_accesibilidad} />

                {prop.justificacion_score && (
                  <p className="text-xs text-gray-500 leading-relaxed">{prop.justificacion_score}</p>
                )}

                {/* Criterios */}
                {prop.criterios_detectados && (
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    {Object.entries(CRITERIOS_LABEL).map(([key, label]) => {
                      const detectado = prop.criterios_detectados?.[key]
                      return (
                        <div key={key} className={`flex items-center gap-2 text-xs px-2 py-1 rounded-lg ${detectado ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-400'}`}>
                          <span>{detectado ? '✓' : '–'}</span>
                          <span>{label}</span>
                        </div>
                      )
                    })}
                  </div>
                )}

                {!prop.analizado && (
                  <button
                    onClick={handleAnalyze}
                    disabled={analyzing}
                    className="w-full mt-2 py-2 px-4 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                  >
                    {analyzing ? 'Analizando con IA...' : '🤖 Analizar con Claude AI'}
                  </button>
                )}
              </div>

              {/* Descripción */}
              {prop.descripcion && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-1">Descripción</h3>
                  <p className="text-sm text-gray-600 leading-relaxed line-clamp-5">{prop.descripcion}</p>
                </div>
              )}

              {/* Link */}
              <a
                href={prop.permalink_ml}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full text-center py-2.5 px-4 rounded-xl border border-gray-200 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Ver publicación original →
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
