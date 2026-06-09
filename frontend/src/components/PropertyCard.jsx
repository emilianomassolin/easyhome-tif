import { SCORE_COLOR } from './ScoreBar'

const FUENTE_LABEL = {
  zonaprop:    'ZonaProp',
  mendozaprop: 'MendozaProp',
  argenprop:   'Argenprop',
}

export default function PropertyCard({ prop, onClick, isFavorite, onToggleFavorite }) {
  const foto  = prop.fotos_urls?.[0]
  const score = prop.score_accesibilidad
  const color = score != null ? SCORE_COLOR(score) : 'var(--c-text3)'
  const pct   = score != null ? Math.min((score / 10) * 100, 100) : 0

  return (
    <div
      onClick={onClick}
      className="overflow-hidden cursor-pointer"
      style={{
        backgroundColor: 'var(--c-surface)',
        borderRadius: 20,
        boxShadow: '0 2px 8px rgba(0,0,0,0.07), 0 0 1px rgba(0,0,0,0.06)',
        transition: 'box-shadow 0.2s ease, transform 0.2s ease, background-color 0.25s ease',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 10px 32px rgba(0,0,0,0.14), 0 0 1px rgba(0,0,0,0.06)'
        e.currentTarget.style.transform = 'translateY(-3px)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.07), 0 0 1px rgba(0,0,0,0.06)'
        e.currentTarget.style.transform = 'translateY(0)'
      }}
    >
      {/* Imagen */}
      <div className="relative overflow-hidden" style={{ height: 180, borderRadius: '20px 20px 0 0' }}>
        {foto ? (
          <img src={foto} alt={prop.titulo} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-5xl"
            style={{ backgroundColor: 'var(--c-surface2)' }}>🏠</div>
        )}

        {/* Fuente */}
        <span
          className="absolute top-3 left-3 text-xs font-semibold px-2 py-1 rounded-full"
          style={{ background: 'var(--c-frosted)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', color: 'var(--c-text)' }}
        >
          {FUENTE_LABEL[prop.fuente] ?? prop.fuente}
        </span>

        {/* Favorito */}
        {onToggleFavorite && (
          <button
            onClick={onToggleFavorite}
            className="absolute top-3 right-3 w-8 h-8 flex items-center justify-center rounded-full transition-transform active:scale-90"
            style={{ background: 'var(--c-frosted)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}
            title={isFavorite ? 'Quitar de favoritas' : 'Guardar en favoritas'}
          >
            <span className="text-base">{isFavorite ? '❤️' : '🤍'}</span>
          </button>
        )}

        {/* Operación */}
        {prop.tipo_operacion && (
          <span
            className={`absolute text-xs font-semibold px-2 py-1 rounded-full ${onToggleFavorite ? 'top-3 right-12' : 'top-3 right-3'}`}
            style={{
              background: prop.tipo_operacion === 'alquiler' ? 'rgba(0,122,255,0.85)' : 'rgba(175,82,222,0.85)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              color: '#FFFFFF',
            }}
          >
            {prop.tipo_operacion === 'alquiler' ? 'Alquiler' : 'Venta'}
          </span>
        )}
      </div>

      {/* Cuerpo */}
      <div className="p-5 space-y-3">
        <h3 className="text-sm font-semibold line-clamp-2 leading-snug" style={{ color: 'var(--c-text)' }}>
          {prop.titulo}
        </h3>

        {prop.ubicacion && (
          <p className="text-xs flex items-center gap-1 truncate" style={{ color: 'var(--c-text2)' }}>
            <span>📍</span><span className="truncate">{prop.ubicacion}</span>
          </p>
        )}

        {prop.precio && (
          <p className="text-lg font-bold tabular-nums" style={{ color: 'var(--c-text)', letterSpacing: '-0.3px' }}>
            ${prop.precio.toLocaleString('es-AR')}
          </p>
        )}

        {/* Score */}
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between">
            <span className="text-xs" style={{ color: 'var(--c-text2)' }}>
              {prop.nivel_accesibilidad ?? 'Sin analizar'}
            </span>
            {score != null && (
              <span className="text-xs font-bold tabular-nums" style={{ color }}>
                {score.toFixed(1)}/10
              </span>
            )}
          </div>
          <div className="h-1 w-full rounded-full overflow-hidden" style={{ backgroundColor: 'var(--c-surface3)' }}>
            <div className="h-1 rounded-full score-bar" style={{ width: `${pct}%`, backgroundColor: color }} />
          </div>
        </div>
      </div>
    </div>
  )
}
