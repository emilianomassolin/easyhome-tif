import ScoreBar from './ScoreBar'

const FUENTE_LABEL = {
  mercadolibre: 'MercadoLibre',
  zonaprop:     'ZonaProp',
  mendozaprop:  'MendozaProp',
}

const FUENTE_COLOR = {
  mercadolibre: 'bg-yellow-100 text-yellow-800',
  zonaprop:     'bg-blue-100 text-blue-800',
  mendozaprop:  'bg-purple-100 text-purple-800',
}

export default function PropertyCard({ prop, onClick }) {
  const foto = prop.fotos_urls?.[0]
  const nivel = prop.nivel_accesibilidad ?? null

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden cursor-pointer hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
    >
      <div className="h-44 bg-gray-100 overflow-hidden">
        {foto
          ? <img src={foto} alt={prop.titulo} className="w-full h-full object-cover" />
          : <div className="w-full h-full flex items-center justify-center text-gray-300 text-4xl">🏠</div>
        }
      </div>

      <div className="p-4 space-y-3">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-sm font-semibold text-gray-800 line-clamp-2 leading-snug">{prop.titulo}</h3>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${FUENTE_COLOR[prop.fuente] ?? 'bg-gray-100 text-gray-600'}`}>
              {FUENTE_LABEL[prop.fuente] ?? prop.fuente}
            </span>
            {prop.tipo_operacion && (
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${prop.tipo_operacion === 'alquiler' ? 'bg-emerald-100 text-emerald-700' : 'bg-orange-100 text-orange-700'}`}>
                {prop.tipo_operacion === 'alquiler' ? 'Alquiler' : 'Venta'}
              </span>
            )}
          </div>
        </div>

        {prop.ubicacion && (
          <p className="text-xs text-gray-500 flex items-center gap-1">
            <span>📍</span>{prop.ubicacion}
          </p>
        )}

        {prop.precio && (
          <p className="text-base font-bold text-gray-900">
            ${prop.precio.toLocaleString('es-AR')}
          </p>
        )}

        <ScoreBar score={prop.score_accesibilidad} nivel={nivel} />
      </div>
    </div>
  )
}
