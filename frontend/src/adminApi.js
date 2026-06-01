const BASE = '/api/admin'

function headers(token) {
  return { 'X-Admin-Token': token, 'Content-Type': 'application/json' }
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
  exportCSV: (token, params = {}) => {
    const q = new URLSearchParams({ ...params })
    return `${BASE}/properties/export?${q}&x_admin_token_header=${token}`
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
  getScraperLogs: (token, fuente) => {
    const q = fuente ? `?fuente=${fuente}` : ''
    return req(token, `/scrapers/logs${q}`)
  },

  // Usuarios
  getUsers: (token) => req(token, '/users'),
  setUserStatus: (token, id, activo) =>
    req(token, `/users/${id}/status?activo=${activo}`, { method: 'PATCH' }),
}
