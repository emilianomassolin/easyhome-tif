const BASE = (import.meta.env.VITE_API_URL || '') + '/api/admin'

function headers(token) {
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
}

async function req(token, path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, { ...opts, headers: headers(token) })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Error en la solicitud')
  }
  return res.json()
}

export const adminApi = {
  // Dashboard
  getDashboard: (token) => req(token, '/dashboard'),

  // Propiedades
  getProperties: (token, params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') q.append(k, v) })
    return req(token, `/properties?${q}`)
  },
  reanalyzeProperty: (token, id) => req(token, `/properties/${id}/reanalyze`, { method: 'POST' }),
  setPropertyStatus: (token, id, activa) =>
    req(token, `/properties/${id}/status?activa=${activa}`, { method: 'PATCH' }),
  updateAccessibility: (token, id, override) =>
    req(token, `/properties/${id}/accessibility`, { method: 'PATCH', body: JSON.stringify({ override }) }),
  exportCSV: async (token, params = {}) => {
    const q = new URLSearchParams({ ...params })
    const res = await fetch(`${BASE}/properties/export?${q}`, { headers: headers(token) })
    if (!res.ok) throw new Error('Error al exportar')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'propiedades.csv'; a.click()
    URL.revokeObjectURL(url)
  },

  // Reportes
  getReports: (token, estado) => {
    const q = estado ? `?estado=${estado}` : ''
    return req(token, `/reports${q}`)
  },
  resolveReport: (token, id, accion, notas = '') => {
    const q = new URLSearchParams({ accion })
    if (notas) q.append('notas', notas)
    return req(token, `/reports/${id}?${q}`, { method: 'PATCH' })
  },
  createReport: (token, property_id, motivo, descripcion = '') => {
    const q = new URLSearchParams({ property_id, motivo })
    if (descripcion) q.append('descripcion', descripcion)
    return req(token, `/reports?${q}`, { method: 'POST' })
  },

  // Scrapers
  runScraper: (token, fuente) => req(token, `/scrapers/${fuente}/run`, { method: 'POST' }),
  getScraperStreamUrl: (token, run_id) => `${BASE}/scrapers/${run_id}/stream?token=${encodeURIComponent(token)}`,
  clearScraperLogs: (token) => req(token, '/scrapers/logs', { method: 'DELETE' }),
  getScraperLogs: (token, fuente) => {
    const q = fuente ? `?fuente=${fuente}` : ''
    return req(token, `/scrapers/logs${q}`)
  },

  // Análisis
  startAnalysis: (token, workers = 10) => req(token, `/analysis/start?workers=${workers}`, { method: 'POST' }),
  getAnalysisStreamUrl: (token, run_id) => `${BASE}/analysis/${run_id}/stream?token=${encodeURIComponent(token)}`,
  getAnalysisStatus: (token) => req(token, '/analysis/status'),

  // Usuarios
  getUsers: (token) => req(token, '/users'),
  setUserStatus: (token, id, activo) =>
    req(token, `/users/${id}/status?activo=${activo}`, { method: 'PATCH' }),

  // Timeline
  getTimeline: (token, fuente, granularidad = 'dia') => {
    const q = new URLSearchParams()
    if (fuente) q.append('fuente', fuente)
    if (granularidad) q.append('granularidad', granularidad)
    return req(token, `/timeline?${q}`)
  },

  // Comentarios (moderación)
  getComments: (token, params = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') q.append(k, v) })
    return req(token, `/comments?${q}`)
  },
  deleteComment: (token, id) => req(token, `/comments/${id}`, { method: 'DELETE' }),
}
