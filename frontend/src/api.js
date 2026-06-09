const BASE = (import.meta.env.VITE_API_URL || '') + '/api'

export async function getProperties({ skip = 0, limit = 20, fuente, min_score, tipo_operacion, solo_analizados, zona, tipo_propiedad, criterios, orden } = {}) {
  const params = new URLSearchParams({ skip, limit })
  if (fuente) params.append('fuente', fuente)
  if (min_score !== undefined && min_score !== '') params.append('min_score', min_score)
  if (tipo_operacion) params.append('tipo_operacion', tipo_operacion)
  if (solo_analizados) params.append('solo_analizados', 'true')
  if (zona) params.append('zona', zona)
  if (tipo_propiedad) params.append('tipo_propiedad', tipo_propiedad)
  if (criterios && criterios.length > 0) params.append('criterios', criterios.join(','))
  if (orden) params.append('orden', orden)
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

export async function getStats() {
  const res = await fetch(`${BASE}/stats`)
  if (!res.ok) throw new Error('Error al cargar stats')
  return res.json()
}

export async function getComments(propertyId) {
  const res = await fetch(`${BASE}/properties/${propertyId}/comments`)
  if (!res.ok) throw new Error('Error al cargar comentarios')
  return res.json()
}

export async function addComment(propertyId, texto, token) {
  const res = await fetch(`${BASE}/properties/${propertyId}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ texto }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Error al comentar')
  }
  return res.json()
}

export async function deleteComment(commentId, token) {
  const res = await fetch(`${BASE}/comments/${commentId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Error al eliminar comentario')
  return res.json()
}

export async function getVotosCriterios(propertyId) {
  const res = await fetch(`${BASE}/properties/${propertyId}/votos_criterios`)
  if (!res.ok) return {}
  return res.json()
}

export async function votarCriterio(propertyId, criterio, valor, token) {
  const res = await fetch(`${BASE}/properties/${propertyId}/votar_criterio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ criterio, valor }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Error al votar')
  }
  return res.json()
}
