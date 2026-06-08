import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../store/auth'

export default function Login() {
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuth()
  const navigate = useNavigate()

  async function handleLogin(e) {
    e.preventDefault()
    if (pin.length !== 4) return
    setLoading(true)
    setError('')
    try {
      const data = await api.login(pin)
      if (!data.is_admin) {
        setError('Acesso restrito a administradores.')
        return
      }
      localStorage.setItem('gnr_admin_token', data.access_token)
      setAuth(data.access_token, data)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'PIN incorreto.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0B1929]">
      {/* Background pattern */}
      <div className="absolute inset-0 overflow-hidden opacity-5">
        <div className="absolute inset-0" style={{
          backgroundImage: 'repeating-linear-gradient(0deg, #fff 0px, #fff 1px, transparent 1px, transparent 40px), repeating-linear-gradient(90deg, #fff 0px, #fff 1px, transparent 1px, transparent 40px)'
        }} />
      </div>

      <div className="relative w-full max-w-sm px-6">
        {/* Logo / Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-[#1A3A5C] to-[#0B1929] border border-[#2E7FD4]/30 shadow-2xl mb-6">
            <span className="text-4xl">🚓</span>
          </div>
          <h1 className="text-3xl font-display font-bold text-white tracking-tight">
            Portal Admin
          </h1>
          <p className="text-[#C9A84C] text-sm font-medium mt-1 tracking-widest uppercase">
            Guarda Nacional Republicana
          </p>
          <p className="text-slate-500 text-xs mt-1">
            Posto Territorial de Famalicão
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-slate-400 text-xs font-medium mb-2 tracking-wider uppercase">
              PIN de Acesso
            </label>
            <input
              type="password"
              value={pin}
              onChange={e => setPin(e.target.value.slice(0, 4))}
              maxLength={4}
              placeholder="• • • •"
              className="w-full px-4 py-3.5 bg-[#1A3A5C]/50 border border-[#2E7FD4]/20 rounded-xl text-white text-center text-2xl tracking-[0.5em] placeholder-slate-600 focus:outline-none focus:border-[#2E7FD4]/60 focus:bg-[#1A3A5C]/70 transition-all"
              autoFocus
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
              <span>⚠️</span> {error}
            </div>
          )}

          <button
            type="submit"
            disabled={pin.length !== 4 || loading}
            className="w-full py-3.5 bg-[#2E7FD4] hover:bg-[#1A6BC4] disabled:bg-[#2E7FD4]/30 disabled:cursor-not-allowed text-white font-semibold font-display rounded-xl transition-all duration-200 shadow-lg shadow-[#2E7FD4]/20"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                A entrar...
              </span>
            ) : 'ENTRAR'}
          </button>
        </form>
      </div>
    </div>
  )
}
