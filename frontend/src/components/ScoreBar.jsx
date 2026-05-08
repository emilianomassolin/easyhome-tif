const NIVELES = {
  'Muy accesible':          { color: 'bg-green-500',  text: 'text-green-700',  bg: 'bg-green-50'  },
  'Accesible':              { color: 'bg-lime-500',   text: 'text-lime-700',   bg: 'bg-lime-50'   },
  'Parcialmente accesible': { color: 'bg-yellow-500', text: 'text-yellow-700', bg: 'bg-yellow-50' },
  'Poco accesible':         { color: 'bg-red-400',    text: 'text-red-700',    bg: 'bg-red-50'    },
}

export default function ScoreBar({ score, nivel }) {
  if (score === null || score === undefined) {
    return (
      <span className="text-xs text-gray-400 italic">Sin analizar</span>
    )
  }

  const estilo = NIVELES[nivel] ?? NIVELES['Poco accesible']
  const pct = Math.min((score / 10) * 100, 100)

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${estilo.bg} ${estilo.text}`}>
          {nivel ?? 'Sin nivel'}
        </span>
        <span className="text-sm font-bold text-gray-700">{score.toFixed(1)}/10</span>
      </div>
      <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-2 rounded-full transition-all ${estilo.color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
