import { useState, useEffect } from 'react'
import { authApi } from '../authApi'
import { useAuth } from '../context/AuthContext'

const CRITERIOS = [
  { id: 'rampa',                    label: '♿ Rampa de acceso'       },
  { id: 'ascensor',                 label: '🛗 Ascensor'              },
  { id: 'bano_adaptado',            label: '🚿 Baño adaptado'         },
  { id: 'entrada_ancha',            label: '🚪 Entrada ancha'         },
  { id: 'estacionamiento_adaptado', label: '🅿️ Estacionamiento PMD'  },
  { id: 'ducha_nivel_piso',         label: '🚿 Ducha italiana'        },
  { id: 'pasamanos',                label: '🪜 Pasamanos'             },
  { id: 'planta_baja',              label: '🏠 Planta baja'           },
]

const ZONAS = [
  'Capital', 'Godoy Cruz', 'Las Heras', 'Guaymallén', 'Maipú',
  'Luján de Cuyo', 'San Rafael', 'Rivadavia', 'Junín', 'General Alvear',
  'San Martín', 'La Paz', 'Santa Rosa', 'Tunuyán', 'Tupungato',
  'San Carlos', 'Malargüe', 'Lavalle',
]

export default function ProfileModal({ onClose }) {
  const { user, token, logout } = useAuth()
  const [tab, setTab] = useState('perfil') // perfil | preferencias | reportes
  const [prefs, setPrefs] = useState(null)
  const [myReports, setMyReports] = useState([])
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (!token) return
    authApi.getPreferences(token).then(setPrefs).catch(() => {})
    authApi.getMyReports(token).then(r => setMyReports(r.reportes || [])).catch(() => {})
  }, [token])

  function toggleCriterio(id) {
    setPrefs(p => {
      const list = p?.criterios || []
      return {
        ...p,
        criterios: list.includes(id) ? list.filter(c => c !== id) : [...list, id],
      }
    })
  }

  async function savePrefs() {
    setSaving(true); setMsg('')
    try {
      await authApi.savePreferences(token, prefs)
      setMsg('Preferencias guardadas')
    } catch (e) { setMsg(`Error: ${e.message}`) }
    finally { setSaving(false) }
  }

  const estadoColor = { pendiente: '#FF9500', resuelto: 'var(--c-green)', ignorado: 'var(--c-text3)' }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(12px)' }}
      onClick={onClose}>
      <div className="w-full max-w-lg rounded-3xl overflow-hidden"
        style={{ backgroundColor: 'var(--c-surface)', border: '1px solid var(--c-border)', maxHeight: '90vh' }}
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="px-6 pt-6 pb-0">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold" style={{ color: 'var(--c-text)' }}>Mi perfil</h2>
              <p className="text-sm" style={{ color: 'var(--c-text2)' }}>{user?.email}</p>
            </div>
            <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-full"
              style={{ backgroundColor: 'var(--c-surface3)', color: 'var(--c-text2)' }}>✕</button>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b" style={{ borderColor: 'var(--c-border)' }}>
            {[['perfil', 'Perfil'], ['preferencias', 'Accesibilidad'], ['reportes', 'Mis reportes']].map(([t, label]) => (
              <button key={t} onClick={() => setTab(t)}
                className="px-3 py-2 text-xs font-semibold transition-all"
                style={tab === t
                  ? { color: 'var(--c-blue)', borderBottom: '2px solid var(--c-blue)' }
                  : { color: 'var(--c-text3)' }}>
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="px-6 py-5 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 160px)' }}>

          {/* Perfil */}
          {tab === 'perfil' && (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold"
                  style={{ backgroundColor: 'var(--c-blue)', color: '#fff' }}>
                  {(user?.nombre || user?.email || '?')[0].toUpperCase()}
                </div>
                <div>
                  <p className="font-semibold" style={{ color: 'var(--c-text)' }}>{user?.nombre || 'Sin nombre'}</p>
                  <p className="text-sm" style={{ color: 'var(--c-text2)' }}>{user?.email}</p>
                </div>
              </div>
              <div style={{ height: 1, backgroundColor: 'var(--c-sep)' }} />
              <button onClick={() => { logout(); onClose() }}
                className="w-full py-2.5 rounded-xl text-sm font-semibold"
                style={{ backgroundColor: 'rgba(255,59,48,0.1)', color: '#FF3B30' }}>
                Cerrar sesión
              </button>
            </div>
          )}

          {/* Preferencias de accesibilidad */}
          {tab === 'preferencias' && prefs && (
            <div className="space-y-5">
              <div>
                <p className="text-xs font-semibold mb-2" style={{ color: 'var(--c-text2)' }}>
                  Criterios que priorizás
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {CRITERIOS.map(({ id, label }) => {
                    const sel = (prefs.criterios || []).includes(id)
                    return (
                      <button key={id} onClick={() => toggleCriterio(id)}
                        className="px-3 py-2.5 rounded-xl text-xs font-medium text-left transition-all"
                        style={sel
                          ? { backgroundColor: 'rgba(10,132,255,0.15)', color: 'var(--c-blue)', border: '1px solid rgba(10,132,255,0.3)' }
                          : { backgroundColor: 'var(--c-surface2)', color: 'var(--c-text2)', border: '1px solid var(--c-border)' }
                        }>
                        {label}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div>
                <p className="text-xs font-semibold mb-2" style={{ color: 'var(--c-text2)' }}>Zona preferida</p>
                <select value={prefs.zona || ''} onChange={e => setPrefs(p => ({ ...p, zona: e.target.value || null }))}
                  className="apple-select w-full">
                  <option value="">Cualquier zona</option>
                  {ZONAS.map(z => <option key={z} value={z}>{z}</option>)}
                </select>
              </div>

              <div>
                <p className="text-xs font-semibold mb-2" style={{ color: 'var(--c-text2)' }}>Tipo de operación</p>
                <div className="flex gap-2">
                  {[['', 'Cualquiera'], ['alquiler', 'Alquiler'], ['venta', 'Venta']].map(([v, l]) => (
                    <button key={v} onClick={() => setPrefs(p => ({ ...p, operacion: v || null }))}
                      className="flex-1 py-2 rounded-xl text-xs font-semibold transition-all"
                      style={prefs.operacion === (v || null)
                        ? { backgroundColor: 'var(--c-blue)', color: '#fff' }
                        : { backgroundColor: 'var(--c-surface2)', color: 'var(--c-text2)', border: '1px solid var(--c-border)' }
                      }>
                      {l}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {[['precio_min', 'Precio mínimo'], ['precio_max', 'Precio máximo']].map(([k, label]) => (
                  <div key={k}>
                    <p className="text-xs font-semibold mb-1" style={{ color: 'var(--c-text2)' }}>{label}</p>
                    <input type="number" placeholder="$" value={prefs[k] || ''}
                      onChange={e => setPrefs(p => ({ ...p, [k]: e.target.value ? +e.target.value : null }))}
                      className="w-full px-3 py-2 rounded-xl text-sm outline-none"
                      style={{ backgroundColor: 'var(--c-input-bg)', border: '1px solid var(--c-input-border)', color: 'var(--c-text)' }}
                    />
                  </div>
                ))}
              </div>

              {msg && (
                <p className="text-xs" style={{ color: msg.startsWith('Error') ? '#FF3B30' : 'var(--c-green)' }}>{msg}</p>
              )}

              <button onClick={savePrefs} disabled={saving}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
                style={{ backgroundColor: 'var(--c-blue)' }}>
                {saving ? 'Guardando…' : 'Guardar preferencias'}
              </button>
            </div>
          )}

          {/* Mis reportes */}
          {tab === 'reportes' && (
            <div className="space-y-3">
              {!myReports.length ? (
                <p className="text-center py-8 text-sm" style={{ color: 'var(--c-text3)' }}>
                  No enviaste reportes todavía
                </p>
              ) : myReports.map(r => (
                <div key={r.id} className="rounded-2xl p-4"
                  style={{ backgroundColor: 'var(--c-surface2)', border: '1px solid var(--c-border)' }}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: 'var(--c-text)' }}>
                        {r.titulo_propiedad}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--c-text2)' }}>{r.motivo}</p>
                      {r.descripcion && (
                        <p className="text-xs mt-1" style={{ color: 'var(--c-text3)' }}>{r.descripcion}</p>
                      )}
                      {r.notas_admin && (
                        <p className="text-xs mt-1 px-2 py-1 rounded-lg"
                          style={{ backgroundColor: 'rgba(52,199,89,0.1)', color: 'var(--c-green)' }}>
                          Admin: {r.notas_admin}
                        </p>
                      )}
                    </div>
                    <span className="text-[11px] font-semibold px-2 py-1 rounded-full shrink-0"
                      style={{ backgroundColor: `${estadoColor[r.estado]}20`, color: estadoColor[r.estado] }}>
                      {r.estado}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
