const BASE = '/api'

export async function getProperties({ skip = 0, limit = 20, fuente, min_score, tipo_operacion, solo_analizados } = {}) {
  const params = new URLSearchParams({ skip, limit })
  if (fuente) params.append('fuente', fuente)
  if (min_score !== undefined && min_score !== '') params.append('min_score', min_score)
  if (tipo_operacion) params.append('tipo_operacion', tipo_operacion)
  if (solo_analizados) params.append('solo_analizados', 'true')
  const res = await fetch(`${BASE}/properties?${params}`)
  if (!res.ok) throw new Error('Error al cargar propiedades')
  return res.json()
}

export async function getProperty(id) {
  const res = await fetch(`${BASE}/properties/${id}`)
  if (!res.ok) throw new Error('Propiedad no encontrada')
  return res.json()
}

export async function analyzeProperty(id) {
  const res = await fetch(`${BASE}/analyze/${id}`, { method: 'POST' })
  if (!res.ok) throw new Error('Error al analizar')
  return res.json()
}
