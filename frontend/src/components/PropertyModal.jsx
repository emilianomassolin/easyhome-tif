import { useState, useEffect } from 'react'
import { getProperty, analyzeProperty } from '../api'
import { SCORE_COLOR } from './ScoreBar'

const CRITERIOS_LABEL = {
  rampa:                    { icon: '♿', label: 'Rampa de acceso'      },
  ascensor:                 { icon: '🛗', label: 'Ascensor'             },
  bano_adaptado:            { icon: '🚿', label: 'Baño adaptado'        },
  entrada_ancha:            { icon: '🚪', label: 'Entrada ancha'        },
  estacionamiento_adaptado: { icon: '🅿️', label: 'Estacionamiento PMD' },
  ducha_nivel_piso:         { icon: '🚿', label: 'Ducha italiana'       },
  pasamanos:                { icon: '🪜', label: 'Pasamanos'            },
  planta_baja:              { icon: '🏠', label: 'Planta baja'          },
}

const FUENTE_LABEL = {
  mercadolibre: 'MercadoLibre',
  zonaprop:     'ZonaProp',
  mendozaprop:  'MendozaProp',
  argenprop:    'Argenprop',
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
    } catch (e) { setError(e.message) }
    finally { setAnalyzing(false) }
  }

  const score = prop?.score_accesibilidad
  const color = score != null ? SCORE_COLOR(score) : 'var(--c-text3)'
  const pct   = score != null ? Math.min((score / 10) * 100, 100) : 0

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)' }}
      onClick={onClose}
    >
      <div
        className="w-full sm:max-w-2xl overflow-y-auto"
        style={{
          backgroundColor: 'var(--c-surface)',
          borderRadius: '24px 24px 0 0',
          maxHeight: '92vh',
          transition: 'background-color 0.25s ease',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Handle mobile */}
        <div className="flex justify-center pt-3 pb-1 sm:hidden">
          <div className="w-10 h-1 rounded-full" style={{ backgroundColor: 'var(--c-surface3)' }} />
        </div>

        {loading && (
          <div className="h-80 flex flex-col items-center justify-center gap-3" style={{ color: 'var(--c-text3)' }}>
            <div className="w-7 h-7 rounded-full border-2 border-t-transparent animate-spin"
              style={{ borderColor: 'var(--c-blue)', borderTopColor: 'transparent' }} />
            <p className="text-sm">Cargando...</p>
          </div>
        )}

        {error && (
          <div className="h-80 flex items-center justify-center text-sm" style={{ color: '#FF453A' }}>{error}</div>
        )}

        {prop && !loading && (
          <>
            {/* Galería */}
            <div className="relative overflow-hidden group" style={{ height: 280, borderRadius: '24px 24px 0 0' }}>
              {prop.fotos_urls?.length > 0 ? (
                <img src={prop.fotos_urls[fotoIdx]} alt={prop.titulo} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-6xl"
                  style={{ backgroundColor: 'var(--c-surface2)' }}>🏠</div>
              )}

              <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent" />

              {prop.fotos_urls?.length > 1 && (
                <>
                  <button
                    onClick={() => setFotoIdx(i => (i - 1 + prop.fotos_urls.length) % prop.fotos_urls.length)}
                    className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full text-white text-xl opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ background: 'var(--c-frosted-dark)', backdropFilter: 'blur(8px)' }}
                  >‹</button>
                  <button
                    onClick={() => setFotoIdx(i => (i + 1) % prop.fotos_urls.length)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 flex items-center justify-center rounded-full text-white text-xl opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ background: 'var(--c-frosted-dark)', backdropFilter: 'blur(8px)' }}
                  >›</button>
                  <span
                    className="absolute bottom-4 right-4 text-xs font-medium px-2.5 py-1 rounded-full"
                    style={{ background: 'var(--c-frosted-dark)', backdropFilter: 'blur(8px)', color: 'rgba(255,255,255,0.9)' }}
                  >
                    {fotoIdx + 1}/{prop.fotos_urls.length}
                  </span>
                </>
              )}

              <button
                onClick={onClose}
                className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full text-white"
                style={{ background: 'var(--c-frosted-dark)', backdropFilter: 'blur(8px)' }}
              >✕</button>
            </div>

            <div className="p-6 space-y-6">
              {/* Badges + título */}
              <div className="space-y-2.5">
                <div className="flex items-center gap-2 flex-wrap">
                  {prop.tipo_operacion && (
                    <span className="text-xs font-semibold px-3 py-1 rounded-full" style={{
                      backgroundColor: prop.tipo_operacion === 'alquiler' ? 'rgba(10,132,255,0.15)' : 'rgba(191,90,242,0.15)',
                      color: prop.tipo_operacion === 'alquiler' ? 'var(--c-blue)' : 'var(--c-purple)',
                    }}>
                      {prop.tipo_operacion === 'alquiler' ? 'Alquiler' : 'Venta'}
                    </span>
                  )}
                  <span className="text-xs font-medium px-3 py-1 rounded-full"
                    style={{ backgroundColor: 'var(--c-surface2)', color: 'var(--c-text2)' }}>
                    {FUENTE_LABEL[prop.fuente] ?? prop.fuente}
                  </span>
                </div>

                <h2 className="text-xl font-bold leading-snug" style={{ color: 'var(--c-text)', letterSpacing: '-0.3px' }}>
                  {prop.titulo}
                </h2>

                {prop.ubicacion && (
                  <p className="text-sm flex items-center gap-1.5" style={{ color: 'var(--c-text2)' }}>
                    <span>📍</span>{prop.ubicacion}
                  </p>
                )}
              </div>

              {/* Precio */}
              {prop.precio && (
                <p className="text-3xl font-bold tabular-nums" style={{ color: 'var(--c-text)', letterSpacing: '-0.5px' }}>
                  ${prop.precio.toLocaleString('es-AR')}
                </p>
              )}

              {/* Separador */}
              <div style={{ height: 1, backgroundColor: 'var(--c-sep)' }} />

              {/* Accesibilidad */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold" style={{ color: 'var(--c-text)' }}>Accesibilidad</h3>
                  {score != null && (
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-bold tabular-nums" style={{ color, letterSpacing: '-0.5px' }}>
                        {score.toFixed(1)}
                      </span>
                      <span className="text-sm font-medium" style={{ color: 'var(--c-text3)' }}>/10</span>
                    </div>
                  )}
                </div>

                {score != null && (
                  <>
                    <div>
                      <p className="text-sm font-medium mb-2" style={{ color: 'var(--c-text2)' }}>{prop.nivel_accesibilidad}</p>
                      <div className="h-1.5 w-full rounded-full overflow-hidden" style={{ backgroundColor: 'var(--c-surface3)' }}>
                        <div className="h-1.5 rounded-full score-bar" style={{ width: `${pct}%`, backgroundColor: color }} />
                      </div>
                    </div>

                    {/* Criterios */}
                    {prop.criterios_detectados && (
                      <div className="grid grid-cols-2 gap-2">
                        {Object.entries(CRITERIOS_LABEL).map(([key, { icon, label }]) => {
                          const detectado = prop.criterios_detectados?.[key]
                          return (
                            <div
                              key={key}
                              className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl"
                              style={{
                                backgroundColor: detectado ? 'rgba(48,209,88,0.1)' : 'var(--c-surface2)',
                                color: detectado ? 'var(--c-green)' : 'var(--c-text3)',
                              }}
                            >
                              <span className="text-base">{icon}</span>
                              <span className="font-medium text-xs flex-1">{label}</span>
                              {detectado && (
                                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                                  <circle cx="7" cy="7" r="7" fill="var(--c-green)" />
                                  <path d="M4 7l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}

                    {prop.justificacion_score && (
                      <p className="text-xs leading-relaxed" style={{ color: 'var(--c-text3)' }}>
                        {prop.justificacion_score}
                      </p>
                    )}
                  </>
                )}

                {!prop.analizado && (
                  <button
                    onClick={handleAnalyze}
                    disabled={analyzing}
                    className="w-full py-3 px-4 rounded-xl text-sm font-semibold text-white transition-opacity disabled:opacity-60"
                    style={{ backgroundColor: 'var(--c-blue)' }}
                  >
                    {analyzing ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="w-4 h-4 rounded-full border-2 border-white/40 border-t-white animate-spin" />
                        Analizando con IA...
                      </span>
                    ) : '🤖 Analizar accesibilidad con Claude AI'}
                  </button>
                )}
              </div>

              {/* Separador */}
              <div style={{ height: 1, backgroundColor: 'var(--c-sep)' }} />

              {/* Descripción */}
              {prop.descripcion && (
                <div className="space-y-2">
                  <h3 className="text-base font-semibold" style={{ color: 'var(--c-text)' }}>Descripción</h3>
                  <p className="text-sm leading-relaxed whitespace-pre-line" style={{ color: 'var(--c-text2)' }}>
                    {prop.descripcion}
                  </p>
                </div>
              )}

              {/* CTA */}
              <a
                href={prop.permalink_ml}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-3.5 px-4 rounded-2xl text-sm font-semibold text-white transition-opacity hover:opacity-90"
                style={{ backgroundColor: 'var(--c-blue)' }}
              >
                Ver publicación original →
              </a>

              <div className="h-2" />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
