const BASE = (import.meta.env.VITE_API_URL || '') + '/api'

function authHeaders(token) {
  return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
}

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Error en la solicitud')
  }
  return res.json()
}

export const authApi = {
  register: (email, password, nombre) =>
    req('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, nombre }),
    }),

  login: (email, password) =>
    req('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),

  me: (token) =>
    req('/auth/me', { headers: authHeaders(token) }),

  forgotPassword: (email) =>
    req('/auth/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token, new_password) =>
    req('/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password }),
    }),

  // Preferencias
  getPreferences: (token) =>
    req('/users/me/preferences', { headers: authHeaders(token) }),

  savePreferences: (token, prefs) =>
    req('/users/me/preferences', {
      method: 'PUT',
      headers: authHeaders(token),
      body: JSON.stringify(prefs),
    }),

  // Favoritas
  getFavoriteIds: (token) =>
    req('/users/me/favorites/ids', { headers: authHeaders(token) }),

  getFavorites: (token) =>
    req('/users/me/favorites', { headers: authHeaders(token) }),

  addFavorite: (token, propertyId) =>
    req(`/users/me/favorites/${propertyId}`, { method: 'POST', headers: authHeaders(token) }),

  removeFavorite: (token, propertyId) =>
    req(`/users/me/favorites/${propertyId}`, { method: 'DELETE', headers: authHeaders(token) }),

  // Reportes
  createReport: (token, property_id, motivo, descripcion) =>
    req('/users/me/reports', {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ property_id, motivo, descripcion }),
    }),

  getMyReports: (token) =>
    req('/users/me/reports', { headers: authHeaders(token) }),
}
