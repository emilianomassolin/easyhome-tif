import { useState } from 'react'
import { authApi } from '../authApi'
import { useAuth } from '../context/AuthContext'

export default function LoginModal({ onClose, initialTab = 'login' }) {
  const { login } = useAuth()
  const [tab, setTab] = useState(initialTab) // login | register | forgot
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [nombre, setNombre] = useState('')
  const [confirmPass, setConfirmPass] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  function reset() { setError(''); setSuccess('') }

  async function handleLogin(e) {
    e.preventDefault(); reset(); setLoading(true)
    try {
      const res = await authApi.login(email, password)
      login(res.access_token, res.user)
      onClose()
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  async function handleRegister(e) {
    e.preventDefault(); reset()
    if (password !== confirmPass) { setError('Las contraseñas no coinciden'); return }
    if (password.length < 6) { setError('La contraseña debe tener al menos 6 caracteres'); return }
    setLoading(true)
    try {
      const res = await authApi.register(email, password, nombre || undefined)
      login(res.access_token, res.user)
      onClose()
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  async function handleForgot(e) {
    e.preventDefault(); reset(); setLoading(true)
    try {
      const res = await authApi.forgotPassword(email)
      setSuccess(res.mensaje)
      if (res._debug_reset_token) {
        setSuccess(`${res.mensaje}\n[Dev] Token: ${res._debug_reset_token}`)
      }
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  const inputClass = "w-full px-3 py-2.5 rounded-xl text-sm outline-none transition-all"
  const inputStyle = {
    backgroundColor: 'var(--c-input-bg)',
    border: '1px solid var(--c-input-border)',
    color: 'var(--c-text)',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(12px)' }}
      onClick={onClose}>
      <div className="w-full max-w-sm rounded-3xl overflow-hidden"
        style={{ backgroundColor: 'var(--c-surface)', border: '1px solid var(--c-border)' }}
        onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="p-6 pb-0">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 flex items-center justify-center rounded-[10px]"
                style={{ background: 'linear-gradient(145deg, #1C1C1E, #3A3A3C)' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M3 11L12 3l9 8v9a1 1 0 01-1 1H5a1 1 0 01-1-1v-9z" fill="white" fillOpacity="0.9"/>
                  <rect x="9" y="14" width="6" height="7" rx="1" fill="#1C1C1E"/>
                  <circle cx="17" cy="8" r="2.5" fill="#34C759"/>
                </svg>
              </div>
              <span className="text-base font-bold" style={{ color: 'var(--c-text)' }}>EasyHome</span>
            </div>
            <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-full text-sm"
              style={{ backgroundColor: 'var(--c-surface3)', color: 'var(--c-text2)' }}>✕</button>
          </div>

          {/* Tabs */}
          {tab !== 'forgot' && (
            <div className="flex rounded-xl p-0.5 mb-5"
              style={{ backgroundColor: 'var(--c-surface2)' }}>
              {[['login', 'Iniciar sesión'], ['register', 'Registrarse']].map(([t, label]) => (
                <button key={t} onClick={() => { setTab(t); reset() }}
                  className="flex-1 py-2 rounded-[9px] text-xs font-semibold transition-all"
                  style={tab === t
                    ? { backgroundColor: 'var(--c-surface)', color: 'var(--c-text)', boxShadow: '0 1px 4px rgba(0,0,0,0.12)' }
                    : { color: 'var(--c-text3)' }}>
                  {label}
                </button>
              ))}
            </div>
          )}

          {tab === 'forgot' && (
            <div className="mb-5">
              <h2 className="text-lg font-bold" style={{ color: 'var(--c-text)' }}>Recuperar contraseña</h2>
              <p className="text-sm mt-1" style={{ color: 'var(--c-text2)' }}>
                Ingresá tu email y te enviaremos un enlace.
              </p>
            </div>
          )}
        </div>

        {/* Forms */}
        <div className="px-6 pb-6">
          {error && (
            <p className="text-xs mb-3 px-3 py-2 rounded-xl" style={{ backgroundColor: 'rgba(255,59,48,0.1)', color: '#FF3B30' }}>
              {error}
            </p>
          )}
          {success && (
            <p className="text-xs mb-3 px-3 py-2 rounded-xl whitespace-pre-line"
              style={{ backgroundColor: 'rgba(52,199,89,0.1)', color: 'var(--c-green)' }}>
              {success}
            </p>
          )}

          {/* Login */}
          {tab === 'login' && (
            <form onSubmit={handleLogin} className="space-y-3">
              <input className={inputClass} style={inputStyle} type="email" placeholder="Email"
                value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
              <input className={inputClass} style={inputStyle} type="password" placeholder="Contraseña"
                value={password} onChange={e => setPassword(e.target.value)} required />
              <button type="submit" disabled={loading}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white transition-opacity disabled:opacity-50"
                style={{ backgroundColor: 'var(--c-blue)' }}>
                {loading ? 'Ingresando…' : 'Iniciar sesión'}
              </button>
              <p className="text-center text-xs" style={{ color: 'var(--c-text3)' }}>
                <button type="button" onClick={() => { setTab('forgot'); reset() }}
                  className="underline" style={{ color: 'var(--c-blue)' }}>
                  ¿Olvidaste tu contraseña?
                </button>
              </p>
            </form>
          )}

          {/* Register */}
          {tab === 'register' && (
            <form onSubmit={handleRegister} className="space-y-3">
              <input className={inputClass} style={inputStyle} type="text" placeholder="Nombre (opcional)"
                value={nombre} onChange={e => setNombre(e.target.value)} autoFocus />
              <input className={inputClass} style={inputStyle} type="email" placeholder="Email"
                value={email} onChange={e => setEmail(e.target.value)} required />
              <input className={inputClass} style={inputStyle} type="password" placeholder="Contraseña (mín. 6 caracteres)"
                value={password} onChange={e => setPassword(e.target.value)} required />
              <input className={inputClass} style={inputStyle} type="password" placeholder="Confirmar contraseña"
                value={confirmPass} onChange={e => setConfirmPass(e.target.value)} required />
              <button type="submit" disabled={loading}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
                style={{ backgroundColor: 'var(--c-blue)' }}>
                {loading ? 'Creando cuenta…' : 'Crear cuenta'}
              </button>
            </form>
          )}

          {/* Forgot */}
          {tab === 'forgot' && !success && (
            <form onSubmit={handleForgot} className="space-y-3">
              <input className={inputClass} style={inputStyle} type="email" placeholder="Tu email"
                value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
              <button type="submit" disabled={loading}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
                style={{ backgroundColor: 'var(--c-blue)' }}>
                {loading ? 'Enviando…' : 'Enviar enlace'}
              </button>
              <p className="text-center text-xs">
                <button type="button" onClick={() => { setTab('login'); reset() }}
                  className="underline" style={{ color: 'var(--c-blue)' }}>
                  Volver al login
                </button>
              </p>
            </form>
          )}
          {tab === 'forgot' && success && (
            <button onClick={() => { setTab('login'); reset() }}
              className="w-full py-2.5 rounded-xl text-sm font-semibold text-white"
              style={{ backgroundColor: 'var(--c-blue)' }}>
              Volver al login
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
