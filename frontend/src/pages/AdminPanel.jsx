import { useState, useEffect, useRef, useCallback } from 'react'
import { adminApi } from '../adminApi'

const TABS = ['Dashboard', 'Propiedades', 'Reportes', 'Scrapers', 'Usuarios']

const FUENTES = ['mercadolibre', 'mendozaprop', 'zonaprop', 'argenprop']

const FUENTE_LABEL = {
  mercadolibre: 'MercadoLibre',
  mendozaprop: 'MendozaProp',
  zonaprop: 'ZonaProp',
  argenprop: 'Argenprop',
}

function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })
}

function Badge({ children, color = 'blue' }) {
  const colors = {
    blue:   { backgroundColor: 'var(--c-blue)',   color: '#fff' },
    green:  { backgroundColor: 'var(--c-green)',  color: '#fff' },
    red:    { backgroundColor: '#FF3B30',          color: '#fff' },
    orange: { backgroundColor: '#FF9500',          color: '#fff' },
    gray:   { backgroundColor: 'var(--c-surface3)', color: 'var(--c-text2)' },
  }
  return (
    <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold" style={colors[color]}>
      {children}
    </span>
  )
}

function Card({ children, className = '' }) {
  return (
    <div className={`rounded-2xl p-4 ${className}`}
      style={{ backgroundColor: 'var(--c-surface)', border: '1px solid var(--c-border)' }}>
      {children}
    </div>
  )
}

function Stat({ label, value, sub, color }) {
  return (
    <Card>
      <p className="text-[11px] font-medium mb-1" style={{ color: 'var(--c-text2)' }}>{label}</p>
      <p className="text-3xl font-bold tabular-nums" style={{ color: color || 'var(--c-text)' }}>
        {value?.toLocaleString('es-AR') ?? '—'}
      </p>
      {sub && <p className="text-[11px] mt-0.5" style={{ color: 'var(--c-text3)' }}>{sub}</p>}
    </Card>
  )
}

function Btn({ children, onClick, variant = 'primary', disabled, small }) {
  const base = `rounded-xl font-semibold transition-all ${small ? 'px-2.5 py-1 text-[11px]' : 'px-4 py-2 text-sm'}`
  const styles = {
    primary: { backgroundColor: 'var(--c-blue)', color: '#fff' },
    danger:  { backgroundColor: '#FF3B30', color: '#fff' },
    ghost:   { backgroundColor: 'var(--c-surface2)', color: 'var(--c-text)', border: '1px solid var(--c-border)' },
    green:   { backgroundColor: 'var(--c-green)', color: '#fff' },
  }
  return (
    <button onClick={onClick} disabled={disabled}
      className={`${base} disabled:opacity-40 disabled:cursor-not-allowed`}
      style={styles[variant]}>
      {children}
    </button>
  )
}

// ── Login ────────────────────────────────────────────────────────────────────

function AdminLogin({ onLogin }) {
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await adminApi.getDashboard(token)
      localStorage.setItem('eh-admin-token', token)
      onLogin(token)
    } catch (err) {
      setError('Token inválido. Verificá el valor de ADMIN_TOKEN en tu .env')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center theme-bg">
      <div className="w-full max-w-sm">
        <Card>
          <div className="text-center mb-6">
            <div className="w-12 h-12 mx-auto mb-3 flex items-center justify-center rounded-2xl"
              style={{ background: 'linear-gradient(145deg, #1C1C1E, #3A3A3C)' }}>
              <span className="text-2xl">⚙️</span>
            </div>
            <h2 className="text-xl font-bold" style={{ color: 'var(--c-text)' }}>Panel Admin</h2>
            <p className="text-sm mt-1" style={{ color: 'var(--c-text2)' }}>EasyHome · Área restringida</p>
          </div>
          <form onSubmit={handleLogin} className="space-y-3">
            <input
              type="password"
              value={token}
              onChange={e => setToken(e.target.value)}
              placeholder="Token de administrador"
              className="w-full px-3 py-2.5 rounded-xl text-sm outline-none"
              style={{
                backgroundColor: 'var(--c-input-bg)',
                border: '1px solid var(--c-input-border)',
                color: 'var(--c-text)',
              }}
              autoFocus
            />
            {error && <p className="text-xs" style={{ color: '#FF3B30' }}>{error}</p>}
            <Btn disabled={!token || loading}>
              {loading ? 'Verificando…' : 'Ingresar'}
            </Btn>
          </form>
        </Card>
      </div>
    </div>
  )
}

// ── Dashboard Tab ─────────────────────────────────────────────────────────────

function DashboardTab({ token }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminApi.getDashboard(token)
      .then(setData)
      .finally(() => setLoading(false))
  }, [token])

  if (loading) return <Loader />
  if (!data) return null

  const estadoColor = { ok: 'green', error: 'red', running: 'blue', sin_datos: 'gray' }

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Propiedades activas" value={data.total_activas} />
        <Stat label="Analizadas" value={data.total_analizadas} color="var(--c-green)" />
        <Stat label="Pendientes análisis" value={data.pendientes_analisis} color="#FF9500" />
        <Stat label="Reportes pendientes" value={data.reportes_pendientes} color="#FF3B30" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Por fuente */}
        <Card>
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--c-text)' }}>
            Propiedades por fuente
          </h3>
          <table className="w-full text-xs">
            <thead>
              <tr style={{ color: 'var(--c-text3)' }}>
                <th className="text-left pb-2">Fuente</th>
                <th className="text-right pb-2">Total</th>
                <th className="text-right pb-2">Analizadas</th>
                <th className="text-right pb-2">Score prom.</th>
              </tr>
            </thead>
            <tbody>
              {data.stats_por_fuente.map(r => (
                <tr key={r.fuente} style={{ borderTop: '1px solid var(--c-border)' }}>
                  <td className="py-2 font-medium" style={{ color: 'var(--c-text)' }}>
                    {FUENTE_LABEL[r.fuente] || r.fuente}
                  </td>
                  <td className="py-2 text-right tabular-nums" style={{ color: 'var(--c-text2)' }}>{r.total}</td>
                  <td className="py-2 text-right tabular-nums" style={{ color: 'var(--c-green)' }}>{r.analizadas}</td>
                  <td className="py-2 text-right tabular-nums" style={{ color: 'var(--c-text)' }}>
                    {r.score_promedio ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {/* Distribución niveles */}
        <Card>
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--c-text)' }}>
            Distribución de niveles
          </h3>
          <div className="space-y-2">
            {data.distribucion_niveles.map(({ nivel, cantidad }) => {
              const total = data.distribucion_niveles.reduce((s, x) => s + x.cantidad, 0)
              const pct = total > 0 ? Math.round(cantidad / total * 100) : 0
              const barColor = nivel === 'Muy accesible' ? 'var(--c-green)' :
                               nivel === 'Accesible' ? '#34C759' :
                               nivel === 'Parcialmente accesible' ? '#FF9500' : '#FF3B30'
              return (
                <div key={nivel}>
                  <div className="flex justify-between text-xs mb-1">
                    <span style={{ color: 'var(--c-text2)' }}>{nivel}</span>
                    <span className="tabular-nums font-medium" style={{ color: 'var(--c-text)' }}>
                      {cantidad} ({pct}%)
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full" style={{ backgroundColor: 'var(--c-surface3)' }}>
                    <div className="h-1.5 rounded-full score-bar" style={{ width: `${pct}%`, backgroundColor: barColor }} />
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      {/* Última ejecución scrapers */}
      <Card>
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--c-text)' }}>
          Última ejecución de scrapers
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {data.ultimas_ejecuciones.map(log => (
            <div key={log.fuente} className="rounded-xl p-3"
              style={{ backgroundColor: 'var(--c-surface2)', border: '1px solid var(--c-border)' }}>
              <p className="text-xs font-semibold mb-1" style={{ color: 'var(--c-text)' }}>
                {FUENTE_LABEL[log.fuente] || log.fuente}
              </p>
              <Badge color={estadoColor[log.estado] || 'gray'}>{log.estado}</Badge>
              <p className="text-[11px] mt-1.5 tabular-nums" style={{ color: 'var(--c-text2)' }}>
                {log.cantidad} props · {fmt(log.inicio)}
              </p>
              {log.mensaje_error && (
                <p className="text-[10px] mt-1 truncate" style={{ color: '#FF3B30' }} title={log.mensaje_error}>
                  {log.mensaje_error}
                </p>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

// ── Propiedades Tab ───────────────────────────────────────────────────────────

function PropertiesTab({ token }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [skip, setSkip] = useState(0)
  const [search, setSearch] = useState('')
  const [fuente, setFuente] = useState('')
  const [analizado, setAnalizado] = useState('')
  const [activa, setActiva] = useState('true')
  const [actionMsg, setActionMsg] = useState('')
  const LIMIT = 50

  const load = useCallback(async (newSkip = 0) => {
    setLoading(true)
    try {
      const params = { skip: newSkip, limit: LIMIT }
      if (search) params.search = search
      if (fuente) params.fuente = fuente
      if (analizado !== '') params.analizado = analizado
      if (activa !== '') params.activa = activa
      const res = await adminApi.getProperties(token, params)
      setData(res)
      setSkip(newSkip)
    } finally {
      setLoading(false) }
  }, [token, search, fuente, analizado, activa])

  useEffect(() => { load(0) }, [load])

  async function handleReanalyze(id) {
    setActionMsg('Analizando…')
    try {
      await adminApi.reanalyzeProperty(token, id)
      setActionMsg('Re-análisis completado')
      load(skip)
    } catch (e) { setActionMsg(`Error: ${e.message}`) }
  }

  async function handleStatus(id, currentActiva) {
    try {
      await adminApi.setPropertyStatus(token, id, !currentActiva)
      setActionMsg(currentActiva ? 'Propiedad dada de baja' : 'Propiedad reactivada')
      load(skip)
    } catch (e) { setActionMsg(`Error: ${e.message}`) }
  }

  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / LIMIT)
  const currentPage = Math.floor(skip / LIMIT) + 1

  return (
    <div className="space-y-4">
      {/* Filtros */}
      <div className="flex flex-wrap gap-2 items-center">
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Buscar por título…"
          className="apple-select text-sm flex-1 min-w-40"
          style={{ borderRadius: 10 }}
        />
        <select value={fuente} onChange={e => setFuente(e.target.value)} className="apple-select">
          <option value="">Todas las fuentes</option>
          {FUENTES.map(f => <option key={f} value={f}>{FUENTE_LABEL[f]}</option>)}
        </select>
        <select value={analizado} onChange={e => setAnalizado(e.target.value)} className="apple-select">
          <option value="">Todos</option>
          <option value="true">Analizadas</option>
          <option value="false">Sin analizar</option>
        </select>
        <select value={activa} onChange={e => setActiva(e.target.value)} className="apple-select">
          <option value="true">Activas</option>
          <option value="false">Inactivas</option>
          <option value="">Todas</option>
        </select>
        <a
          href={`/api/admin/properties/export?activa=${activa}&fuente=${fuente}`}
          className="px-3 py-1.5 rounded-xl text-xs font-semibold"
          style={{ backgroundColor: 'var(--c-surface2)', color: 'var(--c-text)', border: '1px solid var(--c-border)' }}
          download
        >
          ↓ CSV
        </a>
      </div>

      {actionMsg && (
        <p className="text-xs font-medium" style={{ color: 'var(--c-blue)' }}>{actionMsg}</p>
      )}

      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--c-border)', backgroundColor: 'var(--c-surface2)' }}>
                {['ID', 'Título', 'Fuente', 'Score', 'Analizado', 'Estado', 'Fecha', 'Acciones'].map(h => (
                  <th key={h} className="text-left px-3 py-2.5 font-semibold"
                    style={{ color: 'var(--c-text3)', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="text-center py-8" style={{ color: 'var(--c-text3)' }}>Cargando…</td></tr>
              ) : data?.propiedades.map(p => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--c-sep)' }}>
                  <td className="px-3 py-2 tabular-nums" style={{ color: 'var(--c-text3)' }}>{p.id}</td>
                  <td className="px-3 py-2 max-w-xs">
                    <a href={p.permalink_ml} target="_blank" rel="noreferrer"
                      className="font-medium hover:underline line-clamp-1"
                      style={{ color: 'var(--c-text)' }}>
                      {p.titulo}
                    </a>
                    {p.ubicacion && <p className="text-[10px] truncate" style={{ color: 'var(--c-text3)' }}>{p.ubicacion}</p>}
                  </td>
                  <td className="px-3 py-2"><Badge color="gray">{FUENTE_LABEL[p.fuente] || p.fuente}</Badge></td>
                  <td className="px-3 py-2 tabular-nums font-semibold"
                    style={{ color: p.score_accesibilidad >= 6 ? 'var(--c-green)' : p.score_accesibilidad ? '#FF9500' : 'var(--c-text3)' }}>
                    {p.score_accesibilidad ?? '—'}
                  </td>
                  <td className="px-3 py-2">
                    <Badge color={p.analizado ? 'green' : 'gray'}>{p.analizado ? 'Sí' : 'No'}</Badge>
                  </td>
                  <td className="px-3 py-2">
                    <Badge color={p.activa ? 'blue' : 'red'}>{p.activa ? 'Activa' : 'Inactiva'}</Badge>
                  </td>
                  <td className="px-3 py-2 tabular-nums whitespace-nowrap" style={{ color: 'var(--c-text3)' }}>
                    {fmt(p.fecha_creacion)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1">
                      <Btn small variant="ghost" onClick={() => handleReanalyze(p.id)}>⟳</Btn>
                      <Btn small variant={p.activa ? 'danger' : 'green'}
                        onClick={() => handleStatus(p.id, p.activa)}>
                        {p.activa ? 'Dar baja' : 'Activar'}
                      </Btn>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Paginación */}
      {totalPages > 1 && (
        <div className="flex items-center gap-2 justify-center text-xs" style={{ color: 'var(--c-text2)' }}>
          <Btn small variant="ghost" disabled={currentPage === 1} onClick={() => load(skip - LIMIT)}>‹</Btn>
          <span>Página {currentPage} de {totalPages} · {total} propiedades</span>
          <Btn small variant="ghost" disabled={currentPage >= totalPages} onClick={() => load(skip + LIMIT)}>›</Btn>
        </div>
      )}
    </div>
  )
}

// ── Reportes Tab ──────────────────────────────────────────────────────────────

function ReportesTab({ token }) {
  const [tab, setTab] = useState('pendiente')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [resolving, setResolving] = useState(null)
  const [notas, setNotas] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminApi.getReports(token, tab)
      setData(res)
    } finally { setLoading(false) }
  }, [token, tab])

  useEffect(() => { load() }, [load])

  async function handleResolve(id, accion) {
    setResolving(id)
    try {
      await adminApi.resolveReport(token, id, accion, notas)
      setNotas('')
      load()
    } finally { setResolving(null) }
  }

  const estadoColor = { pendiente: 'orange', resuelto: 'green', ignorado: 'gray' }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {['pendiente', 'resuelto', 'ignorado'].map(s => (
          <Btn key={s} small variant={tab === s ? 'primary' : 'ghost'} onClick={() => setTab(s)}>
            {s.charAt(0).toUpperCase() + s.slice(1)}s
          </Btn>
        ))}
      </div>

      {loading ? <Loader /> : (
        <div className="space-y-3">
          {!data?.reportes.length && (
            <p className="text-center py-10 text-sm" style={{ color: 'var(--c-text3)' }}>
              No hay reportes {tab}s
            </p>
          )}
          {data?.reportes.map(r => (
            <Card key={r.id}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-xs font-semibold" style={{ color: 'var(--c-text3)' }}>#{r.id}</span>
                    <Badge color={estadoColor[r.estado]}>{r.estado}</Badge>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: 'var(--c-surface2)', color: 'var(--c-text)' }}>
                      {r.motivo}
                    </span>
                  </div>
                  <p className="text-sm font-medium truncate" style={{ color: 'var(--c-text)' }}>
                    {r.titulo_propiedad}
                  </p>
                  {r.descripcion && (
                    <p className="text-xs mt-0.5" style={{ color: 'var(--c-text2)' }}>{r.descripcion}</p>
                  )}
                  <p className="text-[11px] mt-1" style={{ color: 'var(--c-text3)' }}>
                    {fmt(r.fecha_creacion)}
                    {r.notas_admin && ` · Admin: ${r.notas_admin}`}
                  </p>
                </div>
                {r.estado === 'pendiente' && (
                  <div className="flex flex-col gap-1.5 shrink-0">
                    <input
                      value={notas}
                      onChange={e => setNotas(e.target.value)}
                      placeholder="Nota (opcional)"
                      className="apple-select text-xs w-36"
                    />
                    <Btn small variant="ghost"
                      disabled={resolving === r.id}
                      onClick={() => handleResolve(r.id, 'resolver')}>
                      ✓ Resolver
                    </Btn>
                    <Btn small variant="ghost"
                      disabled={resolving === r.id}
                      onClick={() => handleResolve(r.id, 'ignorar')}>
                      Ignorar
                    </Btn>
                    <Btn small variant="danger"
                      disabled={resolving === r.id}
                      onClick={() => handleResolve(r.id, 'dar_baja')}>
                      Dar de baja
                    </Btn>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Scrapers Tab ──────────────────────────────────────────────────────────────

function ScrapersTab({ token }) {
  const [logs, setLogs] = useState([])
  const [running, setRunning] = useState({})
  const [logOutput, setLogOutput] = useState({})
  const esRefs = useRef({})

  useEffect(() => {
    adminApi.getScraperLogs(token).then(setLogs).catch(() => {})
  }, [token])

  async function handleRun(fuente) {
    setRunning(r => ({ ...r, [fuente]: true }))
    setLogOutput(o => ({ ...o, [fuente]: ['Iniciando scraper…'] }))

    try {
      const { run_id } = await adminApi.runScraper(token, fuente)
      const url = adminApi.getScraperStreamUrl(token, run_id)

      const es = new EventSource(url)
      esRefs.current[fuente] = es

      es.onmessage = (e) => {
        const msg = e.data
        if (msg === '__END__') {
          es.close()
          setRunning(r => ({ ...r, [fuente]: false }))
          adminApi.getScraperLogs(token).then(setLogs).catch(() => {})
        } else {
          setLogOutput(o => ({ ...o, [fuente]: [...(o[fuente] || []), msg] }))
        }
      }
      es.onerror = () => {
        es.close()
        setRunning(r => ({ ...r, [fuente]: false }))
        setLogOutput(o => ({ ...o, [fuente]: [...(o[fuente] || []), '❌ Conexión cerrada'] }))
      }
    } catch (err) {
      setRunning(r => ({ ...r, [fuente]: false }))
      setLogOutput(o => ({ ...o, [fuente]: [...(o[fuente] || []), `❌ ${err.message}`] }))
    }
  }

  const estadoColor = { ok: 'green', error: 'red', running: 'blue', sin_datos: 'gray' }

  return (
    <div className="space-y-6">
      {/* Botones de ejecución */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {FUENTES.map(fuente => {
          const isRunning = !!running[fuente]
          const output = logOutput[fuente] || []
          return (
            <Card key={fuente}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold" style={{ color: 'var(--c-text)' }}>
                  {FUENTE_LABEL[fuente]}
                </h3>
                <Btn small variant={isRunning ? 'ghost' : 'primary'} disabled={isRunning} onClick={() => handleRun(fuente)}>
                  {isRunning ? '⏳ Ejecutando…' : '▶ Ejecutar'}
                </Btn>
              </div>
              {output.length > 0 && (
                <div className="rounded-xl p-3 text-[11px] font-mono max-h-48 overflow-y-auto space-y-0.5"
                  style={{ backgroundColor: 'var(--c-bg)', border: '1px solid var(--c-border)', color: 'var(--c-text2)' }}>
                  {output.map((line, i) => (
                    <p key={i} style={{ color: line.includes('❌') || line.includes('ERROR') ? '#FF3B30' : line.includes('✅') ? 'var(--c-green)' : 'var(--c-text2)' }}>
                      {line}
                    </p>
                  ))}
                </div>
              )}
            </Card>
          )
        })}
      </div>

      {/* Historial */}
      <Card className="overflow-hidden p-0">
        <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--c-border)' }}>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--c-text)' }}>Historial de ejecuciones</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--c-border)', backgroundColor: 'var(--c-surface2)' }}>
                {['Fuente', 'Inicio', 'Fin', 'Estado', 'Propiedades', 'Error'].map(h => (
                  <th key={h} className="text-left px-3 py-2 font-semibold" style={{ color: 'var(--c-text3)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {!logs.length && (
                <tr><td colSpan={6} className="text-center py-6" style={{ color: 'var(--c-text3)' }}>Sin ejecuciones registradas</td></tr>
              )}
              {logs.map(l => (
                <tr key={l.id} style={{ borderBottom: '1px solid var(--c-sep)' }}>
                  <td className="px-3 py-2 font-medium" style={{ color: 'var(--c-text)' }}>{FUENTE_LABEL[l.fuente] || l.fuente}</td>
                  <td className="px-3 py-2 tabular-nums whitespace-nowrap" style={{ color: 'var(--c-text2)' }}>{fmt(l.inicio)}</td>
                  <td className="px-3 py-2 tabular-nums whitespace-nowrap" style={{ color: 'var(--c-text2)' }}>{fmt(l.fin)}</td>
                  <td className="px-3 py-2"><Badge color={estadoColor[l.estado] || 'gray'}>{l.estado}</Badge></td>
                  <td className="px-3 py-2 tabular-nums text-center" style={{ color: 'var(--c-text)' }}>{l.cantidad}</td>
                  <td className="px-3 py-2 max-w-xs">
                    {l.mensaje_error && (
                      <span className="truncate block" style={{ color: '#FF3B30' }} title={l.mensaje_error}>
                        {l.mensaje_error}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

// ── Usuarios Tab ──────────────────────────────────────────────────────────────

function UsuariosTab({ token }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setData(await adminApi.getUsers(token)) }
    finally { setLoading(false) }
  }, [token])

  useEffect(() => { load() }, [load])

  async function handleStatus(id, activo) {
    await adminApi.setUserStatus(token, id, !activo)
    load()
  }

  return (
    <div className="space-y-4">
      {loading ? <Loader /> : (
        <>
          <p className="text-sm" style={{ color: 'var(--c-text2)' }}>
            {data?.total ?? 0} usuarios registrados
          </p>
          {!data?.usuarios.length ? (
            <Card>
              <p className="text-center py-6 text-sm" style={{ color: 'var(--c-text3)' }}>
                No hay usuarios registrados aún
              </p>
            </Card>
          ) : (
            <Card className="overflow-hidden p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--c-border)', backgroundColor: 'var(--c-surface2)' }}>
                      {['ID', 'Email', 'Nombre', 'Estado', 'Registrado', 'Última actividad', 'Acciones'].map(h => (
                        <th key={h} className="text-left px-3 py-2.5 font-semibold" style={{ color: 'var(--c-text3)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.usuarios.map(u => (
                      <tr key={u.id} style={{ borderBottom: '1px solid var(--c-sep)' }}>
                        <td className="px-3 py-2 tabular-nums" style={{ color: 'var(--c-text3)' }}>{u.id}</td>
                        <td className="px-3 py-2 font-medium" style={{ color: 'var(--c-text)' }}>{u.email}</td>
                        <td className="px-3 py-2" style={{ color: 'var(--c-text2)' }}>{u.nombre || '—'}</td>
                        <td className="px-3 py-2">
                          <Badge color={u.activo ? 'green' : 'red'}>{u.activo ? 'Activo' : 'Inactivo'}</Badge>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap" style={{ color: 'var(--c-text2)' }}>{fmt(u.fecha_registro)}</td>
                        <td className="px-3 py-2 whitespace-nowrap" style={{ color: 'var(--c-text2)' }}>{fmt(u.ultima_actividad)}</td>
                        <td className="px-3 py-2">
                          <Btn small variant={u.activo ? 'danger' : 'green'}
                            onClick={() => handleStatus(u.id, u.activo)}>
                            {u.activo ? 'Desactivar' : 'Activar'}
                          </Btn>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

// ── Shared ────────────────────────────────────────────────────────────────────

function Loader() {
  return (
    <div className="flex justify-center py-16">
      <div className="w-6 h-6 rounded-full border-2 animate-spin"
        style={{ borderColor: 'var(--c-border)', borderTopColor: 'var(--c-blue)' }} />
    </div>
  )
}

// ── Main AdminPanel ───────────────────────────────────────────────────────────

export default function AdminPanel({ onClose }) {
  const [token, setToken] = useState(() => localStorage.getItem('eh-admin-token') || '')
  const [authenticated, setAuthenticated] = useState(false)
  const [activeTab, setActiveTab] = useState('Dashboard')

  useEffect(() => {
    if (token) {
      adminApi.getDashboard(token)
        .then(() => setAuthenticated(true))
        .catch(() => {
          localStorage.removeItem('eh-admin-token')
          setToken('')
        })
    }
  }, [])

  function handleLogin(t) {
    setToken(t)
    setAuthenticated(true)
  }

  function handleLogout() {
    localStorage.removeItem('eh-admin-token')
    setToken('')
    setAuthenticated(false)
  }

  if (!authenticated) {
    return <AdminLogin onLogin={handleLogin} />
  }

  return (
    <div className="min-h-screen theme-bg">
      {/* Header */}
      <header className="sticky top-0 z-40"
        style={{
          background: 'var(--c-header)',
          backdropFilter: 'saturate(180%) blur(20px)',
          WebkitBackdropFilter: 'saturate(180%) blur(20px)',
          borderBottom: '1px solid var(--c-sep)',
        }}>
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 flex items-center justify-center rounded-[8px]"
              style={{ background: 'linear-gradient(145deg, #1C1C1E, #3A3A3C)' }}>
              <span className="text-sm">⚙️</span>
            </div>
            <div>
              <h1 className="text-[15px] font-bold leading-none" style={{ color: 'var(--c-text)' }}>
                Panel Admin
              </h1>
              <p className="text-[10px]" style={{ color: 'var(--c-text2)' }}>EasyHome</p>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 overflow-x-auto">
            {TABS.map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className="px-3.5 py-1.5 rounded-[9px] text-xs font-semibold whitespace-nowrap transition-all"
                style={activeTab === tab
                  ? { backgroundColor: 'var(--c-blue)', color: '#fff' }
                  : { backgroundColor: 'transparent', color: 'var(--c-text2)' }
                }>
                {tab}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <Btn small variant="ghost" onClick={handleLogout}>Salir</Btn>
            <Btn small variant="ghost" onClick={onClose}>✕ Cerrar</Btn>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {activeTab === 'Dashboard'    && <DashboardTab  token={token} />}
        {activeTab === 'Propiedades'  && <PropertiesTab token={token} />}
        {activeTab === 'Reportes'     && <ReportesTab   token={token} />}
        {activeTab === 'Scrapers'     && <ScrapersTab   token={token} />}
        {activeTab === 'Usuarios'     && <UsuariosTab   token={token} />}
      </main>
    </div>
  )
}
