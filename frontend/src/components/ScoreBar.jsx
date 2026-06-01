export const SCORE_COLOR = score =>
  score >= 8.5 ? 'var(--c-green)' :
  score >= 6   ? '#30D158'        :
  score >= 3.5 ? '#FF9F0A'        :
                 '#FF453A'

const NIVEL_ALPHA = {
  'Muy accesible':          '20',
  'Accesible':              '20',
  'Parcialmente accesible': '20',
  'Poco accesible':         '20',
}

export default function ScoreBar({ score, nivel }) {
  if (score === null || score === undefined) {
    return <span className="text-xs" style={{ color: 'var(--c-text3)' }}>Sin analizar</span>
  }

  const color = SCORE_COLOR(score)
  const pct   = Math.min((score / 10) * 100, 100)

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full" style={{ color, backgroundColor: color + (NIVEL_ALPHA[nivel] ?? '18') }}>
          {nivel ?? 'Sin nivel'}
        </span>
        <span className="text-sm font-bold tabular-nums" style={{ color }}>
          {score.toFixed(1)}<span style={{ color: 'var(--c-text3)', fontWeight: 400 }}>/10</span>
        </span>
      </div>
      <div className="h-1 w-full rounded-full overflow-hidden" style={{ backgroundColor: 'var(--c-surface3)' }}>
        <div
          className="h-1 rounded-full score-bar"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}
