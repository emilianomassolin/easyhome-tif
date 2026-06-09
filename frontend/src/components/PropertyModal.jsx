import { useState, useEffect } from 'react'
import { getProperty, analyzeProperty, getComments, addComment, deleteComment, getVotosCriterios, votarCriterio, eliminarVotoCriterio } from '../api'
import { SCORE_COLOR } from './ScoreBar'
import { useAuth } from '../context/AuthContext'
import { authApi } from '../authApi'

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

const MOTIVOS_REPORTE = [
  'Score incorrecto',
  'Criterio de accesibilidad erróneo',
  'Propiedad ya no disponible',
  'Información desactualizada',
  'Foto no corresponde',
  'Otro',
]

export default function PropertyModal({ id, onClose, onLoginRequired }) {
  const { user, token, favoriteIds, toggleFavorite } = useAuth()
  const [prop, setProp]           = useState(null)
  const [loading, setLoading]     = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError]         = useState(null)
  const [fotoIdx, setFotoIdx]     = useState(0)
  const [showReport, setShowReport] = useState(false)
  const [reportMotivo, setReportMotivo] = useState(MOTIVOS_REPORTE[0])
  const [reportDesc, setReportDesc]   = useState('')
  const [reportSending, setReportSending] = useState(false)
  const [reportMsg, setReportMsg]     = useState('')

  const [comments, setComments]           = useState([])
  const [commentText, setCommentText]     = useState('')
  const [commentSending, setCommentSending] = useState(false)
  const [commentError, setCommentError]   = useState('')

  const [votos, setVotos]               = useState({})
  const [miVoto, setMiVoto]             = useState({})   // criterio → true/false
  const [votando, setVotando]           = useState(null)  // criterio que está en proceso
  const [votoMsg, setVotoMsg]           = useState('')

  useEffect(() => {
    getProperty(id)
      .then(setProp)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
    getComments(id).then(setComments).catch(() => {})
    getVotosCriterios(id).then(setVotos).catch(() => {})
  }, [id])

  async function handleAddComment(e) {
    e.preventDefault()
    if (!user) { onLoginRequired?.(); return }
    const texto = commentText.trim()
    if (!texto) return
    setCommentSending(true)
    setCommentError('')
    try {
      const nuevo = await addComment(id, texto, token)
      setComments(prev => [nuevo, ...prev])
      setCommentText('')
    } catch (err) { setCommentError(err.message) }
    finally { setCommentSending(false) }
  }

  async function handleDeleteComment(commentId) {
    try {
      await deleteComment(commentId, token)
      setComments(prev => prev.filter(c => c.id !== commentId))
    } catch (err) { setCommentError(err.message) }
  }

  async function handleVotar(criterio, valor) {
    if (!user) { onLoginRequired?.(); return }
    if (votando) return
    setVotando(criterio)
    setVotoMsg('')
    try {
      const res = await votarCriterio(id, criterio, valor, token)
      setMiVoto(prev => ({ ...prev, [criterio]: valor }))
      setVotos(prev => {
        const updated = { ...prev }
        if (!updated[criterio]) updated[criterio] = { true: 0, false: 0 }
        updated[criterio] = { ...updated[criterio], [String(valor)]: res.votos }
        return updated
      })
      if (res.applied) {
        setProp(prev => ({
          ...prev,
          criterios_detectados: { ...prev.criterios_detectados, [criterio]: valor },
          score_accesibilidad: res.score ?? prev.score_accesibilidad,
        }))
        setVotoMsg(`¡3 votos alcanzados! El criterio fue ${valor ? 'agregado' : 'eliminado'} automáticamente.`)
      } else {
        setVotoMsg(`Voto registrado. ${res.votos}/3 votos necesarios.`)
      }
    } catch (err) {
      setVotoMsg(err.message)
    } finally {
      setVotando(null)
      setTimeout(() => setVotoMsg(''), 4000)
    }
  }

  async function handleEliminarVoto(criterio) {
    if (votando) return
    setVotando(criterio)
    setVotoMsg('')
    try {
      await eliminarVotoCriterio(id, criterio, token)
      const valorAnterior = miVoto[criterio]
      setMiVoto(prev => { const n = { ...prev }; delete n[criterio]; return n })
      setVotos(prev => {
        const updated = { ...prev }
        if (updated[criterio]) {
          const k = String(valorAnterior)
          updated[criterio] = { ...updated[criterio], [k]: Math.max(0, (updated[criterio][k] || 1) - 1) }
        }
        return updated
      })
      setVotoMsg('Voto eliminado.')
    } catch (err) {
      setVotoMsg(err.message)
    } finally {
      setVotando(null)
      setTimeout(() => setVotoMsg(''), 3000)
    }
  }

  const isFavorite = favoriteIds.has(id)

  async function handleToggleFavorite() {
    if (!user) { onLoginRequired?.(); return }
    await toggleFavorite(id)
  }

  async function handleSendReport(e) {
    e.preventDefault()
    if (!user) { onLoginRequired?.(); return }
    setReportSending(true)
    try {
      await authApi.createReport(token, id, reportMotivo, reportDesc)
      setReportMsg('Reporte enviado. Te notificaremos cuando sea revisado.')
      setReportDesc('')
    } catch (err) { setReportMsg(`Error: ${err.message}`) }
    finally { setReportSending(false) }
  }

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

              <button
                onClick={handleToggleFavorite}
                className="absolute top-4 right-14 w-8 h-8 flex items-center justify-center rounded-full text-white transition-transform active:scale-90"
                style={{ background: 'var(--c-frosted-dark)', backdropFilter: 'blur(8px)' }}
                title={isFavorite ? 'Quitar de favoritas' : 'Guardar en favoritas'}
              >
                {isFavorite ? '❤️' : '🤍'}
              </button>
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
                      <div className="space-y-2">
                        <div className="grid grid-cols-2 gap-2">
                          {Object.entries(CRITERIOS_LABEL).map(([key, { icon, label }]) => {
                            const detectado = prop.criterios_detectados?.[key]
                            const votosKey = votos[key] || { true: 0, false: 0 }
                            const yaVote = key in miVoto
                            const votosContra = detectado ? (votosKey.false || 0) : (votosKey.true || 0)
                            return (
                              <div
                                key={key}
                                className="flex items-center gap-2 px-3 py-2.5 rounded-xl group"
                                style={{
                                  backgroundColor: detectado ? 'rgba(48,209,88,0.1)' : 'var(--c-surface2)',
                                  color: detectado ? 'var(--c-green)' : 'var(--c-text3)',
                                }}
                              >
                                <span className="text-base">{icon}</span>
                                <span className="font-medium text-xs flex-1 leading-tight">{label}</span>
                                {votosContra > 0 && (
                                  <span className="text-xs opacity-60" title={`${votosContra} reporte${votosContra > 1 ? 's' : ''}`}>
                                    {votosContra}/3
                                  </span>
                                )}
                                {user && prop.analizado && (
                                  yaVote ? (
                                    <button
                                      onClick={() => handleEliminarVoto(key)}
                                      disabled={votando === key}
                                      title="Deshacer mi voto"
                                      className="ml-0.5 rounded-full p-0.5 flex-shrink-0 transition-opacity"
                                      style={{
                                        color: detectado ? '#FF3B30' : '#34C759',
                                        background: detectado ? 'rgba(255,59,48,0.12)' : 'rgba(52,199,89,0.12)',
                                        opacity: votando === key ? 0.5 : 1,
                                      }}
                                    >
                                      <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                                        <path d="M2 6.5C2 4 4 2 6.5 2s4.5 2 4.5 4.5S9 11 6.5 11 2 9 2 6.5z" stroke="currentColor" strokeWidth="1.2"/>
                                        <path d="M4.5 6.5h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                                      </svg>
                                    </button>
                                  ) : (
                                    <button
                                      onClick={() => handleVotar(key, !detectado)}
                                      disabled={votando === key}
                                      title={detectado ? 'Reportar: este criterio NO está presente' : 'Reportar: este criterio SÍ está presente'}
                                      className="opacity-0 group-hover:opacity-100 transition-opacity ml-0.5 rounded-full p-0.5 flex-shrink-0"
                                      style={{ color: 'var(--c-text3)' }}
                                    >
                                      {detectado ? (
                                        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                                          <path d="M2.5 2.5l8 8M10.5 2.5l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                                        </svg>
                                      ) : (
                                        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                                          <path d="M6.5 2v9M2 6.5h9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                                        </svg>
                                      )}
                                    </button>
                                  )
                                )}
                              </div>
                            )
                          })}
                        </div>
                        {votoMsg && (
                          <p className="text-xs text-center py-1 px-2 rounded-lg"
                            style={{ color: votoMsg.includes('!') ? 'var(--c-green)' : 'var(--c-text2)', background: 'var(--c-surface2)' }}>
                            {votoMsg}
                          </p>
                        )}
                        {user && prop.analizado && (
                          <p className="text-xs text-center" style={{ color: 'var(--c-text3)' }}>
                            Pasá el cursor sobre un criterio para reportar si es incorrecto o falta uno.
                          </p>
                        )}
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

              {/* Reportar propiedad */}
              <div>
                {!showReport ? (
                  <button onClick={() => setShowReport(true)}
                    className="w-full py-2.5 px-4 rounded-2xl text-sm font-medium transition-opacity"
                    style={{ backgroundColor: 'var(--c-surface2)', color: 'var(--c-text2)', border: '1px solid var(--c-border)' }}>
                    ⚠️ Reportar información incorrecta
                  </button>
                ) : (
                  <div className="rounded-2xl p-4 space-y-3"
                    style={{ backgroundColor: 'var(--c-surface2)', border: '1px solid var(--c-border)' }}>
                    <p className="text-sm font-semibold" style={{ color: 'var(--c-text)' }}>Reportar propiedad</p>
                    {reportMsg ? (
                      <p className="text-sm" style={{ color: reportMsg.startsWith('Error') ? '#FF3B30' : 'var(--c-green)' }}>
                        {reportMsg}
                      </p>
                    ) : (
                      <form onSubmit={handleSendReport} className="space-y-3">
                        <select value={reportMotivo} onChange={e => setReportMotivo(e.target.value)}
                          className="apple-select w-full">
                          {MOTIVOS_REPORTE.map(m => <option key={m} value={m}>{m}</option>)}
                        </select>
                        <textarea value={reportDesc} onChange={e => setReportDesc(e.target.value)}
                          placeholder="Descripción (opcional)"
                          rows={3}
                          className="w-full px-3 py-2 rounded-xl text-sm outline-none resize-none"
                          style={{ backgroundColor: 'var(--c-input-bg)', border: '1px solid var(--c-input-border)', color: 'var(--c-text)' }}
                        />
                        <div className="flex gap-2">
                          <button type="submit" disabled={reportSending}
                            className="flex-1 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
                            style={{ backgroundColor: '#FF9500' }}>
                            {reportSending ? 'Enviando…' : 'Enviar reporte'}
                          </button>
                          <button type="button" onClick={() => setShowReport(false)}
                            className="px-4 py-2 rounded-xl text-sm font-semibold"
                            style={{ backgroundColor: 'var(--c-surface3)', color: 'var(--c-text2)' }}>
                            Cancelar
                          </button>
                        </div>
                      </form>
                    )}
                  </div>
                )}
              </div>

              {/* Comentarios */}
              <div className="rounded-2xl p-4 space-y-3"
                style={{ backgroundColor: 'var(--c-surface2)', border: '1px solid var(--c-border)' }}>
                <p className="text-sm font-semibold" style={{ color: 'var(--c-text)' }}>
                  💬 Comentarios ({comments.length})
                </p>

                {user ? (
                  <form onSubmit={handleAddComment} className="space-y-2">
                    <textarea
                      value={commentText}
                      onChange={e => setCommentText(e.target.value)}
                      placeholder="¿Qué te pareció esta propiedad?"
                      rows={2}
                      maxLength={500}
                      className="w-full px-3 py-2 rounded-xl text-sm outline-none resize-none"
                      style={{ backgroundColor: 'var(--c-input-bg)', border: '1px solid var(--c-input-border)', color: 'var(--c-text)' }}
                    />
                    {commentError && (
                      <p className="text-xs" style={{ color: '#FF3B30' }}>{commentError}</p>
                    )}
                    <button type="submit" disabled={commentSending || !commentText.trim()}
                      className="w-full py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
                      style={{ backgroundColor: 'var(--c-blue)' }}>
                      {commentSending ? 'Enviando…' : 'Comentar'}
                    </button>
                  </form>
                ) : (
                  <button onClick={() => onLoginRequired?.()}
                    className="w-full py-2 rounded-xl text-sm font-medium"
                    style={{ backgroundColor: 'var(--c-surface3)', color: 'var(--c-text2)', border: '1px solid var(--c-border)' }}>
                    Iniciá sesión para comentar
                  </button>
                )}

                {comments.length > 0 ? (
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {comments.map(c => (
                      <div key={c.id} className="rounded-xl p-3 space-y-1"
                        style={{ backgroundColor: 'var(--c-surface3)', border: '1px solid var(--c-border)' }}>
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold" style={{ color: 'var(--c-text)' }}>
                            {c.user_nombre}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs" style={{ color: 'var(--c-text3)' }}>
                              {new Date(c.fecha_creacion).toLocaleDateString('es-AR', { day: '2-digit', month: 'short' })}
                            </span>
                            {user && c.user_id === user.id && (
                              <button onClick={() => handleDeleteComment(c.id)}
                                className="text-xs opacity-60 hover:opacity-100"
                                style={{ color: '#FF3B30' }} title="Eliminar">
                                ✕
                              </button>
                            )}
                          </div>
                        </div>
                        <p className="text-sm" style={{ color: 'var(--c-text2)' }}>{c.texto}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-center py-2" style={{ color: 'var(--c-text3)' }}>
                    Todavía no hay comentarios. ¡Sé el primero!
                  </p>
                )}
              </div>

              <div className="h-2" />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
